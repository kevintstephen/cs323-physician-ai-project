import json
import re

from agents.base import BaseAgent


class CheckInAgent(BaseAgent):
    """
    Reads a structured overnight update against the patient's prior clinical
    context and returns a concise list of significant changes + required actions.

    Output is JSON, not prose — the UI renders it as an action card, not a document.
    """

    @property
    def name(self) -> str:
        return "checkin"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical decision support agent helping an attending physician process an overnight update for a hospitalized patient.

You will receive:
1. The patient's prior clinical context injected as system context (admission findings, open issues, active problems)
2. A structured overnight update (labs, vitals, events, case management status)

Identify what changed clinically, what it means, and what actions are needed now.

Output ONLY valid JSON — no preamble, no markdown fences:

{
  "changes": [
    {
      "finding": "specific one-line description with values (e.g. 'Creatinine 1.8 → 2.1 mg/dL')",
      "significance": "one-sentence clinical interpretation",
      "trend": "worsening" | "improving" | "stable" | "new"
    }
  ],
  "actions": [
    {
      "title": "imperative one-line action (e.g. 'Hold morning Furosemide — Cr rising on diuresis')",
      "type": "lab_order" | "medication_change" | "consult" | "note_item",
      "detail": "1-2 sentence rationale with specific values",
      "urgency": "now" | "today" | "routine"
    }
  ]
}

Rules:
- Only flag changes that are clinically significant — do not list stable expected findings as separate items
- Values must be specific: 'Cr 1.8→2.1 mg/dL' not 'creatinine worsened'
- Actions must reference the finding that drives them
- Do not generate actions for things already addressed at admission
- If the patient is improving as expected with no concerns, return a single 'stable' change and an empty actions list
- Sort actions by urgency: now first, then today, then routine"""

    def format_prompt(self, context: dict) -> str:
        delta = context.get("delta_data", {})
        return f"""Patient: {context.get("patient_id", "?")}

Overnight update:
{json.dumps(delta, indent=2)}

Identify clinically significant changes and required actions."""

    @staticmethod
    def parse_result(content: str) -> dict:
        text = content.strip()
        for attempt in [
            lambda t: json.loads(t),
            lambda t: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t).group(1)),
            lambda t: json.loads(t[t.find("{"):t.rfind("}") + 1]),
        ]:
            try:
                result = attempt(text)
                if isinstance(result, dict):
                    result.setdefault("changes", [])
                    result.setdefault("actions", [])
                    return result
            except (json.JSONDecodeError, AttributeError, ValueError):
                continue
        return {"changes": [], "actions": []}
