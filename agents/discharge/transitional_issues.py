from agents.base import BaseAgent


def _fmt_incidental_findings(reports: list) -> str:
    findings = [
        f"  [{r.modality} {r.body_region}, {r.timestamp[:10]}] "
        f"{'; '.join(r.incidental_findings)} → {r.follow_up_recommendation}"
        for r in reports
        if r.requires_follow_up and r.incidental_findings
    ]
    return "\n".join(findings) if findings else "None identified."


def _fmt_abnormal_at_discharge(trends: list) -> str:
    lines = []
    for t in trends:
        latest = t.latest
        if latest and latest.is_abnormal:
            admit = t.admission_value
            direction = ""
            if admit and admit.value != latest.value:
                direction = (
                    " (improving)" if float(latest.value) < float(admit.value)
                    else " (worsening)"
                ) if _is_numeric(latest.value) and _is_numeric(admit.value) else ""
            lines.append(
                f"  {t.name}: {latest.value} {t.unit} "
                f"[ref {latest.reference_range}]{direction}"
            )
    return "\n".join(lines) if lines else "None."


def _fmt_med_monitoring(meds: list) -> str:
    lines = [
        f"  • {m.name} {m.dose} ({m.status.upper()}): {m.monitoring_needed}"
        for m in meds
        if m.monitoring_needed and m.status != "continued"
    ]
    return "\n".join(lines) if lines else "None."


def _is_numeric(val: str) -> bool:
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


class TransitionalIssuesAgent(BaseAgent):
    """
    Identifies everything that needs follow-up after discharge and assigns
    an owner, timeline, and urgency to each item.

    This is the most trust-sensitive output in the discharge package —
    Hamza called it 'both a workload and a trust problem.' Every item
    must be traceable to its source so the physician can verify it before
    signing.

    Scans five explicit categories:
      1. Labs that are still abnormal at discharge
      2. Incidental imaging findings
      3. New diagnoses made during this hospitalization
      4. Medications requiring post-discharge monitoring
      5. Procedures or referrals discussed but deferred
    """

    @property
    def name(self) -> str:
        return "transitional_issues"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical care transitions specialist identifying every follow-up task the outpatient provider must act on after this hospitalization.

This is the most important and most trust-sensitive section of the discharge package. The physician will review each item individually before signing. Every item must cite its source so the physician can verify it.

Scan five explicit categories — do not skip any:
1. Labs still abnormal at discharge
2. Incidental imaging findings
3. New diagnoses made during this admission
4. Medications requiring post-discharge monitoring or titration
5. Procedures, referrals, or workups discussed but deferred

Output format:

## Transitional Care Issues — DRAFT

**[N] issues identified across [M] categories. Physician must review each before signing.**

---

### URGENT — Act within 1 week

**Issue [N]: [Title]**
- Action required: [Specific test, visit, or intervention]
- Responsible provider: [PCP / Cardiology / Nephrology / etc.]
- Timeframe: [e.g., within 1 week, within 2 weeks]
- Source: [Exactly where this came from — e.g., "Creatinine 1.8 on discharge BMP, baseline 1.5-1.7, new diuretic dose"]
- Context: [Why this matters clinically]
- ⚠ Access note: [Flag if insurance, distance, or social situation may complicate follow-through]

---

### ROUTINE — Act within 1–3 months

[Same format as above]

---

### MONITORING — Ongoing, no fixed deadline

[Same format as above]

---

### Items NOT requiring follow-up (and why)
[List any items that were considered and ruled out — demonstrates thoroughness and helps the physician trust the list is complete]

---

**Physician checklist before signing:**
- [ ] Each item has a named responsible provider
- [ ] Timeframes are realistic given this patient's insurance and access
- [ ] Patient has been counseled on items marked urgent
- [ ] No incidental findings have been left without a follow-up plan"""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]

        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "?")}
PMH: {", ".join(patient.get("pmh", []))}
Discharge diagnosis: {context.get("discharge_diagnosis", "?")}
Discharge disposition: {context.get("discharge_disposition", "?")}

SOCIAL AND ACCESS CONTEXT (critical for realistic follow-up planning):
- Insurance: {context.get("insurance", "Unknown")}
- PCP: {context.get("primary_care_provider", "Unknown")}
- Social support: {context.get("social_support", "Unknown")}
- Functional status at discharge: {context.get("functional_status_at_discharge", "Unknown")}

---

CATEGORY 1 — LABS STILL ABNORMAL AT DISCHARGE:
{_fmt_abnormal_at_discharge(context.get("lab_trends", []))}

---

CATEGORY 2 — INCIDENTAL IMAGING FINDINGS REQUIRING FOLLOW-UP:
{_fmt_incidental_findings(context.get("imaging_reports", []))}

---

CATEGORY 3 — NEW DIAGNOSES THIS ADMISSION (scan discharge diagnosis vs. admitting diagnosis and course):
Admitting diagnosis: {context.get("admitting_diagnosis", "?")}
Discharge diagnosis: {context.get("discharge_diagnosis", "?")}

---

CATEGORY 4 — MEDICATIONS REQUIRING MONITORING:
{_fmt_med_monitoring(context.get("discharge_medications", []))}

---

CATEGORY 5 — DEFERRED PROCEDURES / REFERRALS (from inpatient course and consult notes):
{context.get("inpatient_course", "Not available.")}

---

FULL INPATIENT COURSE (for additional context):
{context.get("inpatient_course", "Not available.")}

MEDICATION RECONCILIATION:
{context.get("medication_reconciliation", "Not available.")}

---

Please identify all transitional care issues, scanning all five categories explicitly."""
