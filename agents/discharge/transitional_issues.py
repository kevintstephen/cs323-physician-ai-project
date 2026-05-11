import json
from agents.base import BaseAgent


class TransitionalIssuesAgent(BaseAgent):
    """
    Identifies what the receiving outpatient provider must follow up on
    and on what timeline. Hamza called this the most stressful part of
    discharge — both a workload and a trust problem.
    """

    @property
    def name(self) -> str:
        return "transitional_issues"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical care transitions assistant identifying follow-up \
tasks for the receiving outpatient provider after a hospital discharge.

Your reader is the primary care physician (PCP) who will manage this patient \
after discharge. They need a clear, prioritized checklist of what to follow up on, \
by when, and why — so nothing falls through the cracks.

Output format:
## Transitional Care Issues — DRAFT

For each issue, use this structure:

**[Issue #N — short title]**
- Follow-up action: [Specific test, visit, or task]
- Timeframe: [e.g., within 3 days / 1 week / 4–6 weeks]
- Responsible provider: [PCP / Cardiology / other specialist]
- Why it matters: [What happened during this hospitalization that makes this necessary]

Order issues by urgency — most time-sensitive first.

End with:
**Return precautions:**
- [1–3 bullets: symptoms that should prompt the patient to return to the ED]

Rules:
- Only identify follow-up issues supported by the hospitalization data — do not \
invent issues not present in the clinical context
- Use evidence-based timeframes where applicable (e.g., BMP within 1 week of \
diuretic dose change, per heart failure guidelines)
- Do not duplicate information already in the discharge summary — reference it, \
don't repeat it
- If a prior hospitalization had a transitional issue that appears unresolved, \
flag it explicitly
- If the data is too sparse to identify meaningful follow-up items, state that \
explicitly rather than guessing"""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context.get("patient_id", "[Not available]")}

Hospital course summary (from prior agent):
{context.get("discharge_summary", "[Not available — verify in chart]")}

Lab results (chronological):
{json.dumps(patient.get("lab_results", []), indent=2)}

Consult notes:
{json.dumps(patient.get("consult_notes", []), indent=2)}

Medication changes during admission:
{json.dumps(patient.get("medications_administered", []), indent=2)}

Home medications (prior to admission):
{json.dumps(patient.get("current_medications", []), indent=2)}

Past medical history:
{json.dumps(patient.get("pmh", []), indent=2)}

Allergies:
{json.dumps(patient.get("allergies", []), indent=2)}

Prior hospitalizations (check for unresolved transitional issues):
{json.dumps(context.get("prior_history", []), indent=2)}

Please identify all transitional care issues for the outpatient provider."""
