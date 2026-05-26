from agents.admission.chart_review import ChartReviewAgent
from agents.admission.lab_interpretation import LabInterpretationAgent
from agents.admission.ed_note_synthesis import EDNoteSynthesisAgent
from agents.admission.consultant_routing import ConsultantRoutingAgent
from agents.admission.note_drafter import NoteDrafterAgent
from agents.admission.action_extraction import ActionExtractionAgent
from agents.admission.prescription import PrescriptionDraftAgent
from agents.safety import SafetyAgent
from workflows.engine import WorkflowStep

# ---------------------------------------------------------------------------
# Admission workflow
#
# Group 1 (parallel): chart_review, lab_interpretation, ed_note_synthesis
# Sequential:         consultant_routing → note_draft
# Group 2 (parallel): safety_check, action_extraction, prescription_draft
#   All three depend only on note_draft + group 1 outputs, not each other.
#   prescription_draft uses generate_with_tools (live FDA + PA lookups) so
#   it typically runs longest, but parallel execution means it sets the
#   ceiling for group 2, not the total runtime.
# ---------------------------------------------------------------------------

ADMISSION_STEPS: list[WorkflowStep] = [
    WorkflowStep(
        name="chart_review",
        agent_class=ChartReviewAgent,
        parallel_group=1,
    ),
    WorkflowStep(
        name="lab_interpretation",
        agent_class=LabInterpretationAgent,
        parallel_group=1,
    ),
    WorkflowStep(
        name="ed_note_synthesis",
        agent_class=EDNoteSynthesisAgent,
        parallel_group=1,
    ),
    WorkflowStep(
        name="consultant_routing",
        agent_class=ConsultantRoutingAgent,
        context_keys=["chart_review", "lab_interpretation", "ed_note_synthesis"],
    ),
    WorkflowStep(
        name="note_draft",
        agent_class=NoteDrafterAgent,
        context_keys=["chart_review", "lab_interpretation", "ed_note_synthesis", "consultant_routing"],
    ),
    WorkflowStep(
        name="safety_check",
        agent_class=SafetyAgent,
        context_keys=["note_draft"],
        parallel_group=2,
    ),
    WorkflowStep(
        name="action_extraction",
        agent_class=ActionExtractionAgent,
        context_keys=[
            "chart_review", "lab_interpretation", "ed_note_synthesis",
            "consultant_routing", "note_draft",
        ],
        parallel_group=2,
    ),
    WorkflowStep(
        name="prescription_draft",
        agent_class=PrescriptionDraftAgent,
        context_keys=[
            "chart_review", "lab_interpretation", "ed_note_synthesis", "note_draft",
        ],
        parallel_group=2,
    ),
]
