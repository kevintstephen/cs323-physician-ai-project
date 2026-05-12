"""
ContextSynthesisAgent — distills completed workflow outputs into a
structured WorkflowRecord for the running patient context.

This agent runs automatically after every workflow. Its output is JSON,
not prose — it's read by the engine, not by the physician. The discipline
of structured output is what keeps the patient context bounded and queryable
rather than growing into another pile of free text.
"""

import json

from agents.base import BaseAgent, AgentOutput


class ContextSynthesisAgent(BaseAgent):
    """
    Reads all outputs from a completed workflow and extracts:
      - A 2–3 sentence summary of what happened clinically
      - Key findings (specific, quantified)
      - Open issues (actionable, specific enough to act on without re-reading the full notes)
      - Resolved issues (only items conclusively addressed)

    Output is strictly JSON so the engine can parse and store it.
    """

    @property
    def name(self) -> str:
        return "context_synthesis"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical documentation synthesizer. Your job is to read a completed workflow's outputs and extract a structured summary for the patient's running medical record.

Output ONLY valid JSON with this exact structure — no preamble, no explanation, no markdown fences:

{
  "summary": "<2-3 sentences: what workflow ran, the clinical situation, and the primary action taken>",
  "key_findings": ["<specific clinical finding>", ...],
  "open_issues": ["<actionable issue with enough detail to act on without re-reading the notes>", ...],
  "resolved_issues": ["<issue conclusively addressed this workflow>", ...]
}

Rules:
- summary: factual, past tense. Include the primary diagnosis/reason and primary action. No filler.
- key_findings: specific and quantified where possible. "BNP 1240 pg/mL" not "elevated BNP". "New moderate mitral regurgitation on echo" not "new echo finding".
- open_issues: each item must name the finding, its value/source, and the required action. Example: "Creatinine 1.8 mg/dL (baseline 1.5–1.7) on new Furosemide 80mg — check BMP in 1 week". If an issue has a specific responsible provider or timeframe, include it.
- resolved_issues: only include items conclusively addressed this workflow. If resolution is uncertain, leave it in open_issues.
- Be conservative: an unresolved issue carried forward is a safety feature, not a flaw."""

    def format_prompt(self, context: dict) -> str:
        outputs_text = "\n\n".join(
            f"=== {step.upper().replace('_', ' ')} ===\n{content}"
            for step, content in context.get("workflow_outputs", {}).items()
        )
        return f"""Workflow completed: {context.get("workflow_name", "unknown")}
Patient: {context.get("patient_id", "?")}

--- WORKFLOW OUTPUTS ---

{outputs_text}

---

Extract the structured JSON summary for this patient's running context."""

    def synthesize(
        self,
        patient_id: str,
        workflow_name: str,
        outputs: dict,
    ) -> tuple[AgentOutput, dict]:
        """
        Runs synthesis and returns (AgentOutput, parsed_record_dict).
        The AgentOutput is used to show the synthesis step in the UI.
        The parsed dict is written into the PatientContext.

        Falls back to a minimal record if the LLM returns unparseable output.
        """
        context = {
            "patient_id": patient_id,
            "workflow_name": workflow_name,
            "workflow_outputs": outputs,
        }
        output = self.run(context, wiki="")

        try:
            import re
            text = output.content.strip()
            # Try direct parse, then code fence, then first { to last }
            parsed = None
            for attempt in [
                lambda t: json.loads(t),
                lambda t: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t).group(1)),
                lambda t: json.loads(t[t.find("{"):t.rfind("}") + 1]),
            ]:
                try:
                    parsed = attempt(text)
                    break
                except (json.JSONDecodeError, AttributeError, ValueError):
                    continue
            if parsed is None:
                raise ValueError("all parse strategies failed")
        except (json.JSONDecodeError, IndexError, ValueError):
            parsed = {
                "summary": f"{workflow_name.replace('_', ' ').title()} completed.",
                "key_findings": [],
                "open_issues": [],
                "resolved_issues": [],
            }

        return output, parsed
