import json
from agents.base import BaseAgent


class ChartReviewAgent(BaseAgent):
    """
    Synthesizes a patient's prior hospitalization history into a concise,
    structured summary. This is the biggest time-sink in admission — going
    through every prior chart entry to understand baseline status.
    """

    @property
    def name(self) -> str:
        return "chart_review"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical chart review assistant supporting an internal medicine resident.

Your job is to synthesize a patient's prior hospitalization history into a structured summary that the admitting physician can scan in under two minutes.

Output format:
## Prior Hospitalization Summary

**Relevant diagnoses (most recent first):**
- [Date] [Diagnosis] — [key treatment / outcome]

**Baseline functional status:**
[What the patient could do at their best: stairs, walking distance, sleep position, ADLs]

**Key trends to watch:**
- [Lab or clinical trend that recurs across admissions]

**Outstanding issues from prior discharges:**
[Anything a prior team asked the PCP to follow up on that may be unresolved]

Be concise. Flag anything that directly informs today's presentation."""

    def format_prompt(self, context: dict) -> str:
        return f"""Patient ID: {context["patient_id"]}

Current presentation:
{json.dumps(context["patient_data"], indent=2)}

Prior hospitalization records:
{json.dumps(context["prior_history"], indent=2)}

Overnight handoff notes:
{context.get("handoff_notes", "None")}

Please produce the prior hospitalization summary."""
