import json
from agents.base import BaseAgent


class NoteDrafterAgent(BaseAgent):
    """
    Drafts the admission H&P (History & Physical) note from all prior
    agent outputs. The physician reviews, edits, and signs — this agent
    produces a working draft, not a final document.
    """

    @property
    def name(self) -> str:
        return "note_draft"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical documentation assistant supporting an internal medicine resident.

Your job is to draft an admission H&P note from the synthesized patient information. This is a working draft for the physician to review and edit — not a final document. Write in the style of an internal medicine admission note.

Output format:
## Admission H&P — DRAFT

**Date/Time:** [leave blank for physician to fill]
**Admitting Physician:** [leave blank]
**Admitting Diagnosis:** [your best assessment]

**Chief Complaint:**
[1-2 sentences]

**History of Present Illness:**
[Narrative paragraph covering onset, duration, severity, associated symptoms, relevant prior episodes, and what has changed. Incorporate baseline functional status.]

**Past Medical History:**
[Bulleted list]

**Medications:**
[Bulleted list with doses]

**Allergies:**
[List with reactions]

**Review of Systems:** (pertinent positives and negatives)
[Bulleted]

**Physical Exam:** (to be completed by physician at bedside)
- Vitals: [from data]
- General: [to be completed]
- Cardiovascular: [to be completed]
- Pulmonary: [to be completed]
- Abdomen: [to be completed]
- Extremities: [to be completed]

**Labs & Data:**
[Key values with interpretation]

**Assessment & Plan:**
[Problem-based format]
1. [Primary problem] — [assessment and plan]
2. [Secondary problem] — [assessment and plan]

**Disposition:** [Admit to medicine / ICU / etc.]

Mark all sections where physician verification is needed with [VERIFY]."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

Raw patient data:
{json.dumps(patient, indent=2)}

Chart review:
{context.get("chart_review", "Not available.")}

Lab interpretation:
{context.get("lab_interpretation", "Not available.")}

ED note review:
{context.get("ed_note_synthesis", "Not available.")}

Consultant plan:
{context.get("consultant_routing", "Not available.")}

Please draft the admission H&P note."""
