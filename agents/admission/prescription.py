"""
PrescriptionDraftAgent — drafts prescription orders from admission notes.

This agent demonstrates genuine tool use: before committing to each
prescription it calls look_up_drug_info (live OpenFDA API), check_prior_auth
(formulary mock), and — when PA is required — get_alternatives.

Output is a JSON array of prescription objects. The physician reviews and
edits each field in the UI before approving; approved orders are routed to
the pharmacy queue.
"""

import json

from agents.base import BaseAgent, AgentOutput
from tools.drug_lookup import TOOL_DEFS, execute_tool


class PrescriptionDraftAgent(BaseAgent):
    """
    Reads admission context and drafts a set of prescription orders.

    Unlike standard agents, this one uses generate_with_tools() so the
    model can call drug lookup tools mid-reasoning before finalizing output.
    The tool-use loop is handled by the LLM backend; this agent just defines
    the system prompt, formats the input, and parses the output.
    """

    @property
    def name(self) -> str:
        return "prescription_draft"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical pharmacist assistant helping an internal medicine physician draft inpatient prescription orders for a newly admitted patient.

Your workflow for EACH drug you decide to prescribe:
1. Call look_up_drug_info to verify dosing and surface any warnings or interactions relevant to this patient's comorbidities.
2. Call check_prior_auth with the patient's insurance, dose, and indication.
3. If check_prior_auth returns pa_required=true, call get_alternatives to identify lower-tier options the physician can consider.

After completing all tool lookups, output ONLY a JSON array — no preamble, no explanation, no markdown fences.

Each prescription object must have exactly these fields:
{
  "drug_name": "generic name",
  "brand_name": "brand name or empty string",
  "dose": "dose with units (e.g. '80 mg')",
  "route": "IV | PO | SQ | topical | inhaled",
  "frequency": "once | twice daily | every 6h | etc.",
  "indication": "specific clinical indication",
  "quantity": "number of doses or days supply",
  "refills": "0",
  "pa_required": true or false,
  "pa_likelihood_pct": integer 0-100 or null if not applicable,
  "pa_notes": "plain-language PA status summary",
  "alternatives": ["alternative 1", "alternative 2"] or [],
  "drug_info_summary": "1-2 sentence summary of relevant warnings/interactions for THIS patient",
  "agent_notes": "clinical rationale: why this drug, why this dose, any monitoring needed"
}

Rules:
- Only prescribe drugs directly indicated by the admission diagnosis, active comorbidities, or acute management needs. Do not add speculative drugs.
- For dose changes vs. home medications, note the change and reason in agent_notes.
- Quantity for inpatient orders: use "inpatient supply" unless it's a discharge script.
- Always set refills to 0 for inpatient orders.
- drug_info_summary must be specific to this patient's comorbidities — flag interactions with their existing medications."""

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient: {patient.get("name", context["patient_id"])}, {patient.get("age", "?")}y {patient.get("sex", "?")}
Insurance: {patient.get("insurance", "unknown")}
Allergies: {json.dumps(patient.get("allergies", []))}
Active comorbidities: {", ".join(patient.get("pmh", []))}
Current home medications: {", ".join(patient.get("current_medications", []))}

Admitting diagnosis: {context.get("ed_notes", "See chart review")}

--- CHART REVIEW ---
{context.get("chart_review", "Not available.")}

--- LAB INTERPRETATION ---
{context.get("lab_interpretation", "Not available.")}

--- ED NOTE SYNTHESIS ---
{context.get("ed_note_synthesis", "Not available.")}

--- ADMISSION NOTE DRAFT ---
{context.get("note_draft", "Not available.")}

Draft the inpatient prescription orders. For each drug: look up FDA label info, check PA, and get alternatives if PA required. Then output the JSON array."""

    def run(self, context: dict, wiki: str = "") -> AgentOutput:
        """
        Override run() to use generate_with_tools() instead of generate().
        Falls back to generate() for backends that don't override generate_with_tools
        at the native level — the base class two-pass fallback handles it.
        """
        response = self.backend.generate_with_tools(
            model=self.model,
            system_prompt=self.system_prompt,
            wiki=wiki,
            user_prompt=self.format_prompt(context),
            tools=TOOL_DEFS,
            tool_executor=execute_tool,
        )
        return AgentOutput(
            agent_name=self.name,
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
        )

    @staticmethod
    def _salvage_objects(text: str) -> list[dict]:
        """Extracts every complete top-level JSON object from `text`.

        Walks the string tracking brace depth (ignoring braces inside string literals)
        so a truncated array still yields whatever objects closed cleanly. Prescription
        objects contain no nested objects, so each balanced {...} is one order."""
        objs: list[dict] = []
        depth = 0
        start_idx = None
        in_str = False
        esc = False
        for i, ch in enumerate(text):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        try:
                            obj = json.loads(text[start_idx:i + 1])
                            if isinstance(obj, dict):
                                objs.append(obj)
                        except (json.JSONDecodeError, ValueError):
                            pass
                        start_idx = None
        return objs

    @staticmethod
    def parse_prescriptions(content: str) -> list[dict]:
        """
        Parses the JSON array from agent output.
        Returns an empty list with an error entry if parsing fails,
        so the UI always has something to render.
        """
        import re

        def _unwrap(result):
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for key in ("prescriptions", "orders", "medications", "items"):
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return None

        text = content.strip()

        # Strategy 1: direct parse
        try:
            found = _unwrap(json.loads(text))
            if found is not None:
                return found
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: code fence
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence:
            try:
                found = _unwrap(json.loads(fence.group(1)))
                if found is not None:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: first '[' to last ']'
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                found = _unwrap(json.loads(text[start:end + 1]))
                if found is not None:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 4: salvage every complete top-level object from a truncated/malformed
        # array. The model can exceed its token budget mid-array, leaving the final object
        # (and the closing ']') cut off — recover the orders that *did* come through whole
        # rather than discarding the entire draft.
        salvaged = PrescriptionDraftAgent._salvage_objects(text)
        if salvaged:
            return salvaged

        return [{
            "drug_name": "Parse error",
            "brand_name": "",
            "dose": "",
            "route": "",
            "frequency": "",
            "indication": "",
            "quantity": "",
            "refills": "0",
            "pa_required": False,
            "pa_likelihood_pct": None,
            "pa_notes": "Agent output could not be parsed. See raw output.",
            "alternatives": [],
            "drug_info_summary": content[:300],
            "agent_notes": "Manual review required.",
        }]
