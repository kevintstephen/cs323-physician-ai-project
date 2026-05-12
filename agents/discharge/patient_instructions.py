from agents.base import BaseAgent


class PatientInstructionsAgent(BaseAgent):
    """
    Writes the after-visit summary (AVS) in plain language for the patient.

    This is the last clinical output before the physician signs the full
    discharge package. Poor AVS quality is a major readmission risk —
    patients who don't understand their discharge instructions are more
    likely to miss follow-up and return to the ED.

    Target reading level: 6th–8th grade.
    No medical jargon without plain-language explanation.
    """

    @property
    def name(self) -> str:
        return "patient_instructions"

    @property
    def system_prompt(self) -> str:
        return """You are a patient education specialist writing discharge instructions for a hospital patient.

Write at a 6th–8th grade reading level. Avoid medical jargon — if you must use a medical term, explain it in plain language immediately after. Use short sentences and bullet points. This document will be handed to the patient and their family at discharge.

The goals of this document:
1. Help the patient understand what happened during their hospital stay
2. Explain their medications clearly, including any changes
3. Tell them exactly what to watch for at home and when to call or return to the ED
4. Make sure they know when and where to follow up

Output format:

## Your Discharge Instructions

**Patient name:** [name]
**Date:** [discharge date]
**Your doctor:** [VERIFY]

---

### What Happened During Your Stay
[2–3 sentences in plain language: what brought them in, what was found, what was done. Avoid abbreviations. E.g., "You came to the hospital because your heart was not pumping fluid out of your body well enough, causing fluid to build up in your lungs and legs."]

---

### Your Medications
**Important changes to your medications:**
[For each changed or new medication, one short paragraph: what it is, why it was changed, and what to watch for. Use the brand name and generic name if the patient may know either.]

**Your full medication list:**
[Simple table: medication name, dose, when to take it, what it's for]

---

### What to Watch For at Home
**Go to the Emergency Room immediately if you have:**
- [Specific warning sign — be concrete, not clinical]
- [...]

**Call your doctor within 24 hours if you notice:**
- [Less urgent but time-sensitive signs]

---

### Your Follow-Up Appointments

| Who to see | Why | When | Phone number |
|---|---|---|---|
| [Provider] | [Plain-language reason] | [Timeframe] | [If known] |

**Important:** [Any note about scheduling — e.g., "Please call to confirm your cardiology appointment has been scheduled before you leave today."]

---

### Taking Care of Yourself at Home
[3–5 practical bullet points: diet, activity, daily monitoring (e.g., weigh yourself every morning), fluid restrictions if relevant]

---

### Questions?
If you have questions about your care, call [VERIFY — hospital/team contact number].
If it is an emergency, call 911 or go to your nearest emergency room."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]

        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "?")}
Discharge date: {context.get("discharge_date", "?")}
Discharge diagnosis (plain-language translation needed): {context.get("discharge_diagnosis", "?")}
Discharge disposition: {context.get("discharge_disposition", "?")}
PCP: {context.get("primary_care_provider", "Unknown")}
Social support: {context.get("social_support", "Unknown")}

---

HOSPITAL COURSE (use this to explain what happened):
{context.get("discharge_summary", context.get("inpatient_course", "Not available."))}

---

MEDICATION CHANGES (explain each one clearly):
{context.get("medication_reconciliation", "Not available.")}

---

TRANSITIONAL ISSUES (use these to write the follow-up section and warning signs):
{context.get("transitional_issues", "Not available.")}

---

Please write the patient discharge instructions."""
