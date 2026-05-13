"""
ActionExtractionAgent — converts admission workflow outputs into a
structured, prioritized action list for the physician.

This is the bridge between agent-generated information and physician action.
Instead of reading six documents, the physician sees a ranked task list:
what to do right now, what to do today, and what can wait.

Runs last in the admission workflow so it can read all prior outputs,
including the safety check.
"""

import json

from agents.base import BaseAgent


# Action types — used for icons and grouping in the UI
ACTION_TYPES = {
    "medication_hold":   ("💊", "Hold Med"),
    "medication_order":  ("💊", "Med Order"),
    "lab_order":         ("🧪", "Lab"),
    "consult":           ("📞", "Consult"),
    "verify":            ("🔍", "Verify"),
    "nursing_order":     ("🩺", "Nursing"),
    "note_item":         ("📝", "Note"),
    "order":             ("📋", "Order"),
}

URGENCY_CONFIG = {
    "now":     ("🔴", "Act Now",   "error"),
    "today":   ("🟡", "Today",     "warning"),
    "routine": ("⚪", "Routine",   "info"),
}


class ActionExtractionAgent(BaseAgent):
    """
    Reads all admission workflow outputs and extracts every required action,
    classified by type and urgency.

    Output is a JSON array — not prose — so the UI can render a task list
    rather than a document. The physician checks items off rather than
    reading paragraphs.
    """

    @property
    def name(self) -> str:
        return "action_extraction"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical workflow assistant extracting the physician's action list from a completed admission workup.

Your job: read all the admission workflow outputs and identify every action the admitting physician must take. Convert information into tasks.

Output ONLY a JSON array — no preamble, no markdown fences, no explanation.

Each action object must have exactly these fields:
{
  "type": "medication_hold" | "medication_order" | "lab_order" | "consult" | "verify" | "nursing_order" | "note_item" | "order",
  "urgency": "now" | "today" | "routine",
  "title": "Imperative one-line action (what to do, not what was found)",
  "detail": "1-2 sentence clinical rationale — why this is needed and what to watch for",
  "source": "chart_review" | "lab_interpretation" | "ed_note_synthesis" | "consultant_routing" | "note_draft" | "safety_check"
}

Urgency definitions:
- "now": Do in the next 1-2 hours. Time-sensitive clinical decision, safety-critical hold, or urgent consult.
- "today": Do before end of shift. Important but not immediately dangerous.
- "routine": Can be addressed within 24-48h or at next scheduled time.

Type definitions:
- medication_hold: Stop or hold a current home medication
- medication_order: Order a new inpatient medication
- lab_order: Order a specific lab or diagnostic test
- consult: Place a specialty consult order
- verify: Something the physician must personally confirm (exam finding, history, old result)
- nursing_order: Instruction for nursing staff (q4h UOP, daily weight, etc.)
- note_item: Something that must be documented in the admission note
- order: Any other order (diet, activity, monitoring)

Rules:
- Extract EVERY action. It is better to over-extract than under-extract.
- Titles must be imperative and specific: "Hold Metformin 500mg BID" not "Metformin may need to be held"
- Include the specific value or finding that drives the action in the title where relevant: "Order BMP in AM — monitor Cr trend on diuresis"
- Safety check flags should become "now" urgency actions.
- Do not include actions already completed (e.g. "start IV Lasix" — the ED already did this).
- Do not create duplicate actions for the same clinical issue."""

    def format_prompt(self, context: dict) -> str:
        # Feed all prior outputs to the agent
        sections = [
            ("CHART REVIEW",        context.get("chart_review", "")),
            ("LAB INTERPRETATION",  context.get("lab_interpretation", "")),
            ("ED NOTE SYNTHESIS",   context.get("ed_note_synthesis", "")),
            ("CONSULTANT ROUTING",  context.get("consultant_routing", "")),
            ("ADMISSION NOTE DRAFT",context.get("note_draft", "")),
            ("SAFETY CHECK",        context.get("safety_check", "")),
        ]
        body = "\n\n".join(
            f"=== {label} ===\n{content}"
            for label, content in sections
            if content.strip()
        )
        patient = context["patient_data"]
        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "")}
Current home meds: {", ".join(patient.get("current_medications", []))}
Allergies: {", ".join(a.get("drug", "") for a in patient.get("allergies", []))}

--- ADMISSION WORKFLOW OUTPUTS ---

{body}

---

Extract every action the admitting physician must take. Output the JSON array."""

    @staticmethod
    def parse_actions(content: str) -> list[dict]:
        """
        Extracts a JSON action list from agent output using five fallback strategies,
        because models often add preamble text despite instructions not to.

        Strategy 1 — direct parse (model obeyed instructions)
        Strategy 2 — extract from ```json ... ``` code fence
        Strategy 3 — find first '[' to last ']' in the full text (most common failure mode)
        Strategy 4 — find first '{' to last '}' (model wrapped array in an object)
        Strategy 5 — walk char-by-char extracting all complete JSON objects
        """
        import sys
        text = content.strip()
        print(f"[action_extraction] parse_actions called, len={len(text)}, "
              f"first_100={repr(text[:100])}", file=sys.stderr)

        def _unwrap(result):
            """Return the list from result, whether it's already a list or wrapped in a dict."""
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for key in ("actions", "action_list", "tasks", "items"):
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return None

        # Strategy 1: direct parse
        try:
            found = _unwrap(json.loads(text))
            if found is not None:
                return found
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: code fence extraction
        import re
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence:
            try:
                found = _unwrap(json.loads(fence.group(1)))
                if found is not None:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: first '[' to last ']' — handles preamble before the array
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                found = _unwrap(json.loads(text[start:end + 1]))
                if found is not None:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 4: first '{' to last '}' — handles object wrapper
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                found = _unwrap(json.loads(text[start:end + 1]))
                if found is not None:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 5: find all complete JSON objects in the text and assemble a list.
        # Handles cases where the model emits objects without an outer array wrapper,
        # or where the outer array is truncated/malformed.
        import re as _re
        objects = []
        depth = 0
        start_idx = None
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start_idx is not None:
                    fragment = text[start_idx:i + 1]
                    try:
                        obj = json.loads(fragment)
                        if isinstance(obj, dict):
                            objects.append(obj)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    start_idx = None
        if objects:
            # If we got exactly one dict that wraps a list, unwrap it
            if len(objects) == 1:
                found = _unwrap(objects[0])
                if found is not None:
                    return found
            # Otherwise treat each parsed object as an action
            return objects

        # All strategies failed — return a single fallback action so the UI
        # degrades gracefully rather than showing nothing
        return [{
            "type": "note_item",
            "urgency": "today",
            "title": "Review admission workflow outputs manually",
            "detail": "Action extraction could not parse agent output. Review full outputs below.",
            "source": "action_extraction",
        }]
