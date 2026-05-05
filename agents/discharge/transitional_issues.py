import json
from agents.base import BaseAgent


class TransitionalIssuesAgent(BaseAgent):
    """
    Identifies what the receiving outpatient provider must follow up on
    and on what timeline. Hamza called this the most stressful part of
    discharge — both a workload and a trust problem.

    TODO: Implement full prompt.
    """

    @property
    def name(self) -> str:
        return "transitional_issues"

    @property
    def system_prompt(self) -> str:
        # TODO: Write full transitional issues prompt with guideline-based timing recommendations
        return """You are a clinical care transitions assistant identifying follow-up tasks for the receiving outpatient provider.

For each issue, specify: what to follow up on, why it matters, the recommended timeframe, and who is responsible.

Output format:
## Transitional Care Issues — DRAFT

**[Issue #1 — e.g., Sodium trending low]**
- Follow-up action: [Specific test or visit]
- Timeframe: [e.g., within 1 week]
- Responsible provider: [PCP / Cardiology / etc.]
- Context: [Why this matters — what happened during hospitalization]

Repeat for each issue. Flag any issue where the patient's insurance situation or follow-up access may be uncertain with ⚠️."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

Hospital course summary:
{context.get("discharge_summary", "Not available.")}

Patient medications: {patient.get("current_medications", [])}
PMH: {patient.get("pmh", [])}

Please identify transitional care issues that the outpatient provider must follow up on."""
