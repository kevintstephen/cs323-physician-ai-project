import json
from agents.base import BaseAgent


class EDNoteSynthesisAgent(BaseAgent):
    """
    Critically reads the ED pass-off and flags gaps, possible misdiagnoses,
    and items the admitting team needs to verify independently.

    As Hamza noted: ED physicians are focused on keeping the patient alive,
    not the full picture. They often misdiagnose. This agent acts as a
    second set of eyes on the ED's assessment.
    """

    @property
    def name(self) -> str:
        return "ed_note_synthesis"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical reasoning assistant supporting an internal medicine resident reviewing an ED pass-off.

ED physicians stabilize patients under high load. Their assessments are starting points, not conclusions. Your job is to critically evaluate the ED's notes and flag what the admitting team needs to independently verify.

Output format:
## ED Note Review

**ED's working diagnosis:** [diagnosis]

**Supports the ED diagnosis:**
- [Evidence from vitals, labs, history]

**Challenges or complicates the ED diagnosis:**
- [Conflicting data, atypical features, missing workup]

**Alternative diagnoses to consider:**
- [Diagnosis] — [supporting rationale]

**Items the admitting team must verify:**
- [Specific exam finding, lab, or history element]

**Key information missing from the ED note:**
- [What wasn't documented that matters]

Be a skeptical collaborator, not a critic. The ED did their job; now help the admitting team do theirs."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

ED pass-off notes:
{context.get("ed_notes", "No ED notes provided.")}

Vitals on arrival:
{json.dumps(patient.get("vitals", {}), indent=2)}

Current labs:
{json.dumps(patient.get("labs", {}), indent=2)}

PMH: {patient.get("pmh", [])}

Please review the ED note and flag what the admitting team needs to verify."""
