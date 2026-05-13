from agents.base import BaseAgent


def _fmt_med_list(meds: list) -> str:
    if not meds:
        return "None"
    lines = []
    for m in meds:
        line = f"  • {m.name} {m.dose} {m.route} {m.frequency} — {m.indication}"
        if m.status != "continued":
            line += f" [{m.status.upper()}]"
        lines.append(line)
    return "\n".join(lines)


class MedicationReconciliationAgent(BaseAgent):
    """
    Compares admission and discharge medication lists and produces a
    structured reconciliation the physician can approve line by line.

    For every medication that changed: what changed, why, and what the
    outpatient provider must monitor. This feeds directly into the
    transitional issues list.
    """

    @property
    def name(self) -> str:
        return "medication_reconciliation"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical pharmacist assistant producing a medication reconciliation for a physician to review at discharge.

The physician will approve this line by line. Format it so changes are immediately obvious and every monitoring requirement is explicit.

Output format:

## Medication Reconciliation — DRAFT

### Changes from Admission to Discharge

For each medication that is NEW, DOSE CHANGED, or DISCONTINUED:

**[Medication name] [dose] [route] [frequency]** — [STATUS]
- Change: [what changed, from what to what]
- Reason: [clinical rationale]
- Monitoring required: [specific lab, timing, and who checks it — or "None"]
- Patient counseling needed: [what to tell the patient about this change, or "Standard"]

---

### Continued Medications (no changes)
[Simple bulleted list: name, dose, frequency]

---

### Medications Held During Admission (restarted or not)
[List with reason held and whether restarted at discharge]

---

### Reconciliation Flags
[Any concerns: drug-drug interactions with new medications, dosing relative to current renal function, medications the patient may need prior auth for, anything the physician must verify before signing]

Flag any item requiring physician attention with ⚠."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        admit_meds = context.get("admission_medications", [])
        dc_meds = context.get("discharge_medications", [])

        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "?")}
PMH: {", ".join(patient.get("pmh", []))}
Allergies: {patient.get("allergies", [])}
Insurance: {context.get("insurance", "Unknown")}

---

ADMISSION MEDICATIONS ({len(admit_meds)} medications):
{_fmt_med_list(admit_meds)}

---

DISCHARGE MEDICATIONS ({len(dc_meds)} medications):
{_fmt_med_list(dc_meds)}

---

MEDICATION CHANGE DETAILS (from data model):
{_fmt_changes(admit_meds, dc_meds)}

---

INPATIENT COURSE CONTEXT (for reconciliation rationale):
{context.get("inpatient_course", "Not available.")}

---

Please produce the medication reconciliation."""


def _fmt_changes(admit_meds: list, dc_meds: list) -> str:
    lines = []
    for m in dc_meds:
        if m.status != "continued":
            line = f"  • {m.name}: {m.status.upper()}"
            if m.change_reason:
                line += f"\n    Reason: {m.change_reason}"
            if m.monitoring_needed:
                line += f"\n    Monitor: {m.monitoring_needed}"
            lines.append(line)
    for m in admit_meds:
        if m.status == "held" and not any(d.name == m.name for d in dc_meds):
            lines.append(
                f"  • {m.name}: HELD during admission ({m.change_reason}) — not restarted"
            )
    return "\n".join(lines) if lines else "No changes detected."
