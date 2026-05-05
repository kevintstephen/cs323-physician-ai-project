from agents.admission.chart_review import ChartReviewAgent
from agents.admission.lab_interpretation import LabInterpretationAgent
from agents.admission.ed_note_synthesis import EDNoteSynthesisAgent
from agents.admission.consultant_routing import ConsultantRoutingAgent
from agents.admission.note_drafter import NoteDrafterAgent
from agents.safety import SafetyAgent
from workflows.engine import WorkflowStep

# ---------------------------------------------------------------------------
# Admission workflow
#
# Triggered when a new patient is assigned from the ED.
# Mirrors the manual process Hamza described: read the chart, check labs,
# critique the ED note, figure out who to call, write the H&P.
#
# Steps 1-3 are independent and could run in parallel (parallel_group=1).
# Steps 4-6 are sequential, each depending on all prior outputs.
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
    ),
]
