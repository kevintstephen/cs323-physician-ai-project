import json
from agents.base import BaseAgent


class ConsultantRoutingAgent(BaseAgent):
    """
    Determines which specialty consultants should be called for this admission
    and drafts a concise, relevant summary to give each one.

    As Hamza noted: when paging a consultant, you need to filter your notes
    down to what *they* care about — a nephrologist doesn't want to hear
    about the patient's hypothyroidism.
    """

    @property
    def name(self) -> str:
        return "consultant_routing"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical coordination assistant supporting an internal medicine resident.

Your job is to identify which specialty consultants are needed for this admission and prepare a tight, relevant summary for each one. Each consultant summary should contain only what that specialty cares about — filter ruthlessly.

Output format:
## Consultant Recommendations

**[Specialty]**
- Reason for consult: [one sentence]
- What they need to know: [relevant vitals, labs, history filtered to their domain]
- Urgency: [Emergent / Urgent / Routine]
- Suggested page content: "[Draft of what to say when paging them]"

Repeat for each recommended consultant.

**Consultants NOT needed (and why):**
- [Specialty]: [brief rationale]

Only recommend consultants where there is a clear clinical indication."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

Chief complaint: {patient.get("chief_complaint", "unknown")}
PMH: {patient.get("pmh", [])}
Current medications: {patient.get("current_medications", [])}

Vitals:
{json.dumps(patient.get("vitals", {}), indent=2)}

Labs:
{json.dumps(patient.get("labs", {}), indent=2)}

Chart review summary:
{context.get("chart_review", "Not available.")}

Lab interpretation:
{context.get("lab_interpretation", "Not available.")}

ED note review:
{context.get("ed_note_synthesis", "Not available.")}

Please identify which consultants are needed and prepare their summaries."""
