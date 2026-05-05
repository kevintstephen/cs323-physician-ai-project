import json
from agents.base import BaseAgent


class DischargeSummaryAgent(BaseAgent):
    """
    Drafts the hospital course summary for the discharge document.

    TODO: Implement full prompt. This stub shows the interface —
    replace the system_prompt and format_prompt with real content.
    """

    @property
    def name(self) -> str:
        return "discharge_summary"

    @property
    def system_prompt(self) -> str:
        # TODO: Write full discharge summary prompt
        return """You are a clinical documentation assistant drafting a hospital course summary for a patient discharge document.

Summarize what happened during this hospitalization in a clear, chronological narrative that the receiving outpatient provider can understand at a glance.

Output format:
## Hospital Course Summary — DRAFT

**Admission date:** [leave blank]
**Discharge date:** [leave blank]
**Admitting diagnosis:**
**Discharge diagnosis:**

**Hospital Course:**
[Narrative: what was found on admission, what was done, how the patient responded, and their status at discharge]

**Discharge condition:** [Stable / Improved / etc.]
**Discharge disposition:** [Home / SNF / Rehab / etc.]
**Discharge medications:** [List with any changes from admission highlighted]"""

    def format_prompt(self, context: dict) -> str:
        # TODO: Pull in the full inpatient course from Epic (labs, notes, orders)
        patient = context["patient_data"]
        return f"""Patient ID: {context["patient_id"]}

Patient data at admission:
{json.dumps(patient, indent=2)}

Please draft the hospital course summary. Note: full inpatient course data from Epic integration is not yet wired up — use available data and mark missing sections with [DATA NEEDED]."""
