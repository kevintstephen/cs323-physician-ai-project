import json
from agents.base import BaseAgent


class CaseManagementCoordinatorAgent(BaseAgent):
    """
    Assesses what post-discharge services a patient needs and drafts
    communication for case managers.

    Per Hamza: patients can sit in the hospital for two weeks because of
    case management hold-ups. This agent is a stub for what will become
    a multi-agent sub-workflow.

    TODO: Break into sub-agents:
      - InsuranceVerificationAgent: what does this patient's plan cover?
      - RehabOptionsAgent: which facilities have availability + accept the insurance?
      - HomeCareAssessmentAgent: does the patient need home O2, visiting nurses, PT?
      - CommunicationDrafterAgent: drafts messages to case managers, insurers, rehabs
    TODO: Add async tracking so multi-day coordination state persists between sessions
    """

    @property
    def name(self) -> str:
        return "case_management_plan"

    @property
    def system_prompt(self) -> str:
        # TODO: Expand with insurance-specific logic and facility lookup
        return """You are a case management assistant supporting an internal medicine senior resident.

Assess what post-discharge services this patient needs and draft a case management plan.

Output format:
## Case Management Assessment — DRAFT

**Discharge readiness:** [Ready / Pending clinical / Pending social]

**Anticipated disposition:** [Home / Home with services / SNF / Inpatient rehab / LTACH]

**Services needed:**
- [ ] Home health / visiting nurse — [reason if applicable]
- [ ] Home oxygen — [reason if applicable]
- [ ] Physical therapy — [reason if applicable]
- [ ] Occupational therapy — [reason if applicable]
- [ ] DME (equipment) — [specify]

**Insurance considerations:**
[What is likely covered vs. likely to require prior auth or appeal — note if unknown]

**Draft message to case manager:**
[A concise message the senior resident can send to initiate case management coordination]

**Potential blockers:**
[Anything that could delay discharge — insurance, family situation, patient preference, availability]"""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

Patient data:
{json.dumps(patient, indent=2)}

Please produce the case management assessment.
Note: Insurance verification and facility availability lookup are not yet automated — flag items that require manual verification with [VERIFY]."""
