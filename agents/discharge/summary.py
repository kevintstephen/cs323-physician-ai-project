import json
from agents.base import BaseAgent


class DischargeSummaryAgent(BaseAgent):
    """
    Drafts the hospital course summary for the discharge document.
    Audience: receiving primary care physician.
    """

    @property
    def name(self) -> str:
        return "discharge_summary"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical documentation assistant drafting a hospital course \
summary for a patient discharge document.

Your reader is the receiving primary care physician (PCP) who was not present \
during this hospitalization. They need to understand what happened, what changed, \
and what requires their follow-up — in 90 seconds or less.

Output format:
## Hospital Course Summary — DRAFT

**Admission date:**
**Discharge date:**
**Length of stay:** [in days; calculate from admission/discharge dates, or "Not available" if either is missing]

**Admitting diagnosis:**
**Discharge diagnosis:**

**Hospital Course:**
[Chronological narrative: what was found on admission, key interventions, \
how the patient responded, and condition at discharge. 2–3 short paragraphs.]

**Significant results:**
- [Lab values, imaging, or procedures that changed management — with dates if available]

**Medication changes:**
- Started: [drug, dose, indication]
- Stopped: [drug, reason]
- Changed: [drug, old → new dose, reason]
- Held during admission, resumed at discharge: [drug, context]

(If no changes from home medications, write 'No changes from home medications.' and omit the subcategories above.)

**Discharge condition:** [Stable / Improved / Guarded]
**Discharge disposition:** [Home / SNF / Rehab / Other]

**What the PCP must know:**
- [1–3 bullets: unresolved issues, pending results, or decisions deferred to outpatient]

Rules:
- Do not copy-paste raw lab values or vitals tables — summarize what they mean clinically
- Do not speculate about diagnoses not supported by the available data
- Do not invent dates, dosages, medication names, or clinical events not present in the context data
- Write for a PCP, not a specialist — avoid unexplained jargon
- If a single field's data is missing, mark it as '[Not available — verify in chart]'
- If most fields are missing and the resulting document would be more '[Not available]' \
markers than substance, state at the top: 'Insufficient data to draft a meaningful summary. \
Available information: [brief description].' rather than filling in a hollow template"""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}
Name: {patient.get("name", "[Not available]")} | Age: {patient.get("age", "[Not available]")} | Sex: {patient.get("sex", "[Not available]")}
Admission date: {patient.get("admission_date", "[Not available — verify in chart]")}
Discharge date: {patient.get("discharge_date", "[Not available — verify in chart]")}
Admitting diagnosis: {patient.get("admitting_diagnosis", "[Not available — verify in chart]")}

Past medical history:
{json.dumps(patient.get("pmh", []), indent=2)}

Allergies:
{json.dumps(patient.get("allergies", []), indent=2)}

Home medications (prior to admission):
{json.dumps(patient.get("current_medications", []), indent=2)}

Vitals at admission:
{json.dumps(patient.get("vitals_at_admission", {}), indent=2)}

ED physician notes:
{context.get("ed_notes", "[Not available — verify in chart]")}

Overnight handoff notes:
{context.get("handoff_notes", "[Not available — verify in chart]")}

Daily progress notes:
{json.dumps(patient.get("daily_progress_notes", []), indent=2)}

Nursing notes:
{json.dumps(patient.get("nursing_notes", []), indent=2)}

Lab results (chronological):
{json.dumps(patient.get("lab_results", []), indent=2)}

Consult notes:
{json.dumps(patient.get("consult_notes", []), indent=2)}

Medications administered:
{json.dumps(patient.get("medications_administered", []), indent=2)}

Prior hospitalizations:
{json.dumps(context.get("prior_history", []), indent=2)}

Please draft the hospital course summary."""
