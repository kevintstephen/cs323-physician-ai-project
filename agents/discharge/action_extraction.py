from agents.base import BaseAgent


class DischargeActionExtractionAgent(BaseAgent):
    """
    Reads all discharge workflow outputs and produces a single, prioritized
    physician sign-off checklist.

    Instead of reading five documents, the physician sees a ranked task list:
    what must be done before the discharge order is placed, before the patient
    leaves, and what must be confirmed as arranged.

    Runs last in the discharge workflow so it can read all prior outputs,
    including the safety check.
    """

    @property
    def name(self) -> str:
        return "discharge_checklist"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical workflow assistant producing a physician sign-off checklist for a hospital discharge.

Your job: read all discharge workflow outputs and extract every action the physician must complete or verify before signing. Convert documents into tasks.

Output format:

## Physician Sign-Off Checklist

### Before placing the discharge order
- [ ] [Specific action — imperative, concrete]

### Before the patient leaves
- [ ] [Specific action]

### Confirm is arranged (can delegate but must verify)
- [ ] [Specific action]

Rules:
- Every item must be imperative and specific: "Confirm BMP is ordered for 1-week follow-up" not "Labs may be needed"
- Every safety flag from the safety check must appear as a checklist item
- Every [VERIFY] tag in any document must become a checklist item with the specific thing to verify
- Every incidental imaging finding must appear with a named responsible provider confirmed
- Medication reconciliation flags marked ⚠ must each become a checklist item
- Do not include actions already completed during the admission
- Do not include generic tasks true of every discharge (e.g., "write discharge order", "print discharge papers") — only patient-specific actions
- Do not duplicate — one item per distinct action
- Consolidate related items: "Confirm BMP and weight check at cardiology follow-up" not two separate items
- Aim for 8–12 items total across all sections. If you have more, consolidate
- Keep items short enough to scan in 2 seconds
- If there are no items in a section, omit that section header"""

    def format_prompt(self, context: dict) -> str:
        sections = [
            ("DISCHARGE SUMMARY",          context.get("discharge_summary", "")),
            ("MEDICATION RECONCILIATION",   context.get("medication_reconciliation", "")),
            ("TRANSITIONAL ISSUES",         context.get("transitional_issues", "")),
            ("SAFETY CHECK",                context.get("safety_check", "")),
        ]
        body = "\n\n".join(
            f"=== {label} ===\n{content}"
            for label, content in sections
            if content.strip()
        )
        patient = context["patient_data"]
        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "")}
Discharge diagnosis: {context.get("discharge_diagnosis", "?")}
Discharge disposition: {context.get("discharge_disposition", "?")}

--- DISCHARGE WORKFLOW OUTPUTS ---

{body}

---

Extract every action the physician must complete or verify before signing the discharge. Output the checklist."""
