from agents.discharge.summary import DischargeSummaryAgent
from agents.discharge.transitional_issues import TransitionalIssuesAgent
from agents.safety import SafetyAgent
from workflows.engine import WorkflowStep

# ---------------------------------------------------------------------------
# Discharge workflow
#
# Triggered when the attending orders discharge.
# The two hardest parts per Hamza:
#   1. Writing a high-quality hospital course summary
#   2. Identifying transitional issues — what the outpatient provider must
#      follow up on, and on what timeline
#
# TODO: Add medication reconciliation agent
# TODO: Add outpatient pharmacy coordination agent
# ---------------------------------------------------------------------------

DISCHARGE_STEPS: list[WorkflowStep] = [
    WorkflowStep(
        name="discharge_summary",
        agent_class=DischargeSummaryAgent,
    ),
    WorkflowStep(
        name="transitional_issues",
        agent_class=TransitionalIssuesAgent,
        context_keys=["discharge_summary"],
    ),
    WorkflowStep(
        name="safety_check",
        agent_class=SafetyAgent,
        context_keys=["discharge_summary", "transitional_issues"],
    ),
]
