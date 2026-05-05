import json
from agents.base import BaseAgent


class LabInterpretationAgent(BaseAgent):
    """
    Interprets the current lab panel in the context of the patient's history
    and chief complaint. Flags critical values and identifies trends.
    """

    @property
    def name(self) -> str:
        return "lab_interpretation"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical lab interpretation assistant supporting an internal medicine resident.

Your job is to read the current lab results alongside the patient's history and flag what matters for today's admission.

Output format:
## Lab Interpretation

**Critical / urgent values:**
- [Lab]: [Value] — [clinical significance]

**Relevant trends (if prior values available):**
- [Lab]: [prior value] → [current value] — [interpretation]

**Labs that support the working diagnosis:**
- [Lab]: [Value] — [reasoning]

**Labs that argue against or complicate the working diagnosis:**
- [Lab]: [Value] — [reasoning]

**Recommended follow-up labs:**
- [Lab] — [reason and timing]

Be direct. Attending-level interpretation, not just reference ranges."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}
Chief complaint: {patient.get("chief_complaint", "unknown")}
PMH: {patient.get("pmh", [])}

Current labs:
{json.dumps(patient.get("labs", {}), indent=2)}

Prior hospitalization context:
{json.dumps(context.get("prior_history", []), indent=2)}

Please interpret the labs in the context of this presentation."""
