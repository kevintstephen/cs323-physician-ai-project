"""
Admission workflow tests.

Run with: pytest tests/ -v

Tests use the EpicClient stub (no real API calls) and mock the Anthropic
client so no API key is needed for unit tests.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context.session import PatientSession, WorkflowState
from tools.epic import EpicClient
from workflows.engine import WorkflowEngine, WorkflowStep
from workflows.admission import ADMISSION_STEPS

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_patient() -> dict:
    return json.loads((FIXTURES_DIR / "sample_patient.json").read_text())


@pytest.fixture
def patient_session(sample_patient) -> PatientSession:
    epic = EpicClient()
    return PatientSession(
        patient_id="TEST-001",
        patient_data=epic.get_patient("TEST-001"),
        prior_history=epic.get_prior_hospitalizations("TEST-001"),
        ed_notes=epic.get_ed_notes("TEST-001"),
        handoff_notes=epic.get_handoff_notes("TEST-001"),
    )


@pytest.fixture
def mock_anthropic_client():
    """Returns a mock Anthropic client that returns a canned response."""
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text="Mock agent output for testing.")]
    response.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
    )
    client.messages.create.return_value = response
    return client


class TestEpicStub:
    def test_get_patient_returns_data(self, sample_patient):
        epic = EpicClient()
        patient = epic.get_patient("TEST-001")
        assert patient["patient_id"] == "TEST-001"
        assert "labs" in patient
        assert "vitals" in patient

    def test_get_prior_hospitalizations(self):
        epic = EpicClient()
        history = epic.get_prior_hospitalizations("TEST-001")
        assert isinstance(history, list)
        assert len(history) > 0
        assert "reason" in history[0]

    def test_get_ed_notes(self):
        epic = EpicClient()
        notes = epic.get_ed_notes("TEST-001")
        assert isinstance(notes, str)
        assert len(notes) > 0


class TestPatientSession:
    def test_session_holds_patient_data(self, patient_session, sample_patient):
        assert patient_session.patient_id == "TEST-001"
        assert patient_session.patient_data["age"] == 67
        assert len(patient_session.prior_history) == 3

    def test_session_has_ed_notes(self, patient_session):
        assert "CHF" in patient_session.ed_notes


class TestWorkflowEngine:
    def test_engine_runs_all_steps(self, patient_session, mock_anthropic_client):
        steps = [
            WorkflowStep(name="step_one", agent_class=_make_stub_agent("step_one")),
            WorkflowStep(name="step_two", agent_class=_make_stub_agent("step_two"), context_keys=["step_one"]),
        ]
        engine = WorkflowEngine(client=mock_anthropic_client, wiki="")
        state = engine.run(steps, patient_session)

        assert state.status == "complete"
        assert "step_one" in state.outputs
        assert "step_two" in state.outputs

    def test_context_keys_are_passed_to_later_steps(self, patient_session, mock_anthropic_client):
        """Verifies that a step's output is available to subsequent steps."""
        captured_contexts = {}

        class CapturingAgent:
            def __init__(self, client):
                self.client = client

            @property
            def name(self):
                return "step_two"

            def run(self, context, wiki=""):
                captured_contexts["step_two"] = context
                from agents.base import AgentOutput
                return AgentOutput(agent_name="step_two", content="captured")

        steps = [
            WorkflowStep(name="step_one", agent_class=_make_stub_agent("step_one")),
            WorkflowStep(name="step_two", agent_class=CapturingAgent, context_keys=["step_one"]),
        ]
        engine = WorkflowEngine(client=mock_anthropic_client, wiki="")
        engine.run(steps, patient_session)

        assert "step_one" in captured_contexts["step_two"]

    def test_admission_workflow_has_correct_steps(self):
        step_names = [s.name for s in ADMISSION_STEPS]
        assert step_names == [
            "chart_review",
            "lab_interpretation",
            "ed_note_synthesis",
            "consultant_routing",
            "note_draft",
            "safety_check",
        ]

    def test_safety_check_is_last(self):
        assert ADMISSION_STEPS[-1].name == "safety_check"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stub_agent(agent_name: str):
    """Creates a minimal agent class that returns a canned string."""
    from agents.base import AgentOutput

    class StubAgent:
        def __init__(self, client):
            self.client = client

        @property
        def name(self):
            return agent_name

        def run(self, context, wiki=""):
            return AgentOutput(agent_name=agent_name, content=f"Output from {agent_name}")

    return StubAgent
