from agents.case_management.coordinator import CaseManagementCoordinatorAgent
from agents.safety import SafetyAgent
from workflows.engine import WorkflowStep

# ---------------------------------------------------------------------------
# Case management workflow
#
# Per Hamza: "Absolute nightmare if we figured out an AI solution it would
# be incredible." Involves coordinating home services, oxygen, rehab,
# insurance verification, PT — all of which can block discharge for days.
#
# This is an async workflow by nature: many steps involve waiting on
# external parties (insurance, rehab facilities, visiting nurses).
#
# Current state: single coordinator agent as a stub.
# TODO: Break into sub-agents — InsuranceVerificationAgent,
#       RehabOptionsAgent, HomeCareAssessmentAgent, CommunicationDrafterAgent
# TODO: Add async state machine for multi-day coordination tracking
# ---------------------------------------------------------------------------

CASE_MANAGEMENT_STEPS: list[WorkflowStep] = [
    WorkflowStep(
        name="case_management_plan",
        agent_class=CaseManagementCoordinatorAgent,
    ),
    WorkflowStep(
        name="safety_check",
        agent_class=SafetyAgent,
        context_keys=["case_management_plan"],
    ),
]
