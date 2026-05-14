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

The physician will scan this in under 60 seconds. Show only what changed and what needs action. Do not repeat information that belongs in the discharge summary or patient instructions.

Output format:

## Medication Reconciliation — DRAFT

**[N] changes | [M] continued unchanged**

---

### Medications Changed

For each NEW, DOSE CHANGED, HELD, or DISCONTINUED medication, use exactly this format:

**[Medication name] [dose] [route] [frequency]** — [NEW / DOSE CHANGED / HELD / DISCONTINUED]
- [1 sentence: what changed and why, citing the clinical reason from the inpatient course]
- Monitor: [specific lab + timing, e.g., "BMP in 1 week" — or "None"]

---

### ⚠ Flags

[Only include if there is a genuine concern. Each flag on one line:]
⚠ [Concern — 1 sentence with specific action needed]

---

### Continued Unchanged ([N])

[Single compact line per medication: name, dose, frequency — no extra detail]

Rules:
- Do not invent medications, doses, or frequencies not present in the medication data
- Do not include patient counseling points here — those belong in the patient instructions
- Do not explain what a medication does unless it is directly relevant to a flag
- If a medication was held during admission and restarted, list it under Changes as HELD → RESTARTED
- If a medication was held and NOT restarted, list it as DISCONTINUED with the reason
- Keep the Continued list compact — if there are more than 10, just list name and dose on one line each
- Every flag must be specific and actionable: "⚠ Furosemide 80mg with current Cr 1.8 — confirm BMP in 1 week" not "⚠ Monitor renal function"
- If there are no flags, omit the Flags section entirely"""

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
