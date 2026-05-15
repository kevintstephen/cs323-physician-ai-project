import dataclasses
import json
from agents.base import BaseAgent


def _fmt_notes(notes: list) -> str:
    if not notes:
        return "None"
    return "\n\n".join(
        f"[{n.timestamp}] {n.author} ({n.author_role}, {n.specialty})\n{n.content}"
        for n in notes
    )


def _fmt_lab_trends(trends: list) -> str:
    if not trends:
        return "None"
    lines = []
    for t in trends:
        values = " → ".join(
            f"{r.value}{'⚠' if r.is_abnormal else ''}" for r in t.results
        )
        ref = t.results[0].reference_range if t.results else "N/A"
        lines.append(f"  {t.name} ({t.unit}) [ref {ref}]: {values}")
    return "\n".join(lines)


def _fmt_imaging(reports: list) -> str:
    if not reports:
        return "None"
    parts = []
    for r in reports:
        block = (
            f"[{r.timestamp}] {r.modality} — {r.body_region.upper()}\n"
            f"Indication: {r.ordering_indication}\n"
            f"Impression: {r.impression}"
        )
        if r.incidental_findings:
            block += f"\n⚠ INCIDENTAL: {'; '.join(r.incidental_findings)}"
            block += f"\n  Follow-up: {r.follow_up_recommendation}"
        parts.append(block)
    return "\n\n".join(parts)


def _fmt_vitals(entries: list) -> str:
    if not entries:
        return "None"
    lines = ["  Date/Time             HR   BP        RR   O2%   Wt(kg)  O2 delivery"]
    for v in entries:
        lines.append(
            f"  {v.timestamp[:16]}  "
            f"{str(v.heart_rate or '—'):5}"
            f"{v.blood_pressure:10}"
            f"{str(v.respiratory_rate or '—'):5}"
            f"{str(v.o2_saturation or '—'):6}"
            f"{str(v.weight_kg or '—'):8}"
            f"{v.o2_delivery}"
        )
    return "\n".join(lines)


class InpatientCourseAgent(BaseAgent):
    """
    Synthesizes the full inpatient course into a structured, day-by-day
    timeline. This is the foundation all other discharge agents read from —
    it transforms raw clinical data into a coherent narrative of what happened,
    what turned, and what remains unresolved at discharge.
    """

    @property
    def name(self) -> str:
        return "inpatient_course"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical documentation assistant synthesizing a patient's full inpatient course for a physician preparing discharge documents.

Your output is not patient-facing — it is a structured clinical summary that other agents and the physician will use as source material. Prioritize completeness and clinical precision over brevity.

Output format:

## Inpatient Course Summary

**Admission:** [date] | **Discharge:** [date] | **LOS:** [N days]
**Admitting diagnosis:** [diagnosis]
**Discharge diagnosis:** [diagnosis]

---

### Clinical Timeline

**Hospital Day 1 — [date]**
- [Key event, clinical decision, or significant finding]
- [Lab result that changed management]
- [Consultant involvement]

[Repeat for each hospital day]

---

### Clinical Turning Points
[Bullet list of the 3-5 moments that most shaped the course: e.g., when diuresis started working, when creatinine peaked, when a new finding changed the plan]

---

### Active Problems at Discharge
For each problem still present at discharge:
**[Problem name]**
- Status at discharge: [resolved / improved / ongoing / new]
- Key events during admission: [1-2 sentences]
- Outstanding at discharge: [anything that still needs follow-up]

---

### Data Summary
**Labs at discharge:** [final values for each trended lab, with trend direction]
**Weight change:** [admission weight] → [discharge weight] ([total change])
**Imaging findings:** [brief summary of key findings including any incidental]
**Medication changes:** [number changed, number new, number discontinued — detail in reconciliation step]

Rules:
- Do not invent clinical events, lab values, dates, or findings not present in the source data. \
Every fact in the timeline must be traceable to a specific note, lab, or imaging report
- If no progress note exists for a hospital day, state 'No documentation available for HD [N]' \
rather than interpolating from adjacent days
- Every incidental imaging finding marked with ⚠ in the input MUST appear in the output — \
these are the items most likely to be lost in transitions of care
- If two sources conflict (e.g., a progress note and consult note disagree on a value or plan), \
flag the discrepancy rather than silently choosing one
- If the input data is too sparse to construct a meaningful timeline (e.g., no progress notes \
and no lab trends), state that explicitly at the top rather than generating a speculative course"""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "?")}
Admission: {context.get("admission_date", "?")} → Discharge: {context.get("discharge_date", "?")} ({context.get("length_of_stay_days", "?")} days)
Admitting diagnosis: {context.get("admitting_diagnosis", "?")}
Discharge diagnosis: {context.get("discharge_diagnosis", "?")}
PMH: {", ".join(patient.get("pmh", []))}

---

PROGRESS NOTES ({len(context.get("progress_notes", []))} notes):

{_fmt_notes(context.get("progress_notes", []))}

---

CONSULT NOTES ({len(context.get("consult_notes", []))} notes):

{_fmt_notes(context.get("consult_notes", []))}

---

LAB TRENDS (chronological, ⚠ = abnormal):

{_fmt_lab_trends(context.get("lab_trends", []))}

---

IMAGING REPORTS:

{_fmt_imaging(context.get("imaging_reports", []))}

---

VITALS TREND:

{_fmt_vitals(context.get("vitals_trend", []))}

---

Please synthesize the inpatient course summary."""
