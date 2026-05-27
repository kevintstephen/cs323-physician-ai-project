"""
WikiSubstrateAgent — extracts new clinical protocols and physician
preferences from a completed workflow to evolve the Doctor's Wiki.

This agent acts as the "learning loop" of the system. It identifies
patterns in the physician's decisions and documentation that aren't
yet explicitly stated in their wiki.
"""

import json
import re
from agents.base import BaseAgent, AgentOutput


class WikiSubstrateAgent(BaseAgent):
    """
    Analyzes workflow outputs and identifies new, implicit rules or preferences.
    Output is strictly JSON for the engine to parse and apply to the wiki.
    """

    @property
    def name(self) -> str:
        return "wiki_substrate"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical knowledge engineer. Your job is to analyze a completed patient workflow and identify new clinical protocols or physician preferences that should be added to the Doctor's Wiki.

The Wiki captures a physician's "cognitive workflow" — not just what they did, but why they did it, what evidence they relied on, and what questions they asked.

Compare the current workflow (especially the physician's final notes and decisions) against the existing Wiki. Look for:
- Specific thresholds used (e.g., "Always check BMP if Cr > 2.0").
- Repeating patterns in management.
- Diagnostic questions asked to reach a conclusion.
- Rationale behind specific choices (especially if they deviate from standard protocols).
- Evidence or guidelines cited.

Output ONLY valid JSON with this exact structure:

{
  "new_protocols": [
    {
      "category": "Diseases/Issues",
      "topic": "Condition Name",
      "rules": [
        {
          "text": "The core rule or protocol step",
          "attributes": {
            "Rationale": "Why the doctor does this",
            "Evidence": "Specific study or guideline if mentioned",
            "Interpretation": "How the doctor interprets the evidence",
            "Diagnostic Questions": "Key questions asked"
          }
        }
      ]
    }
  ],
  "new_preferences": [
    {
      "category": "Communication Style",
      "topic": "Category Name",
      "rules": [
        {
          "text": "The core preference",
          "attributes": {
             "Rationale": "Why this preference exists"
          }
        }
      ]
    }
  ]
}

Rules:
- Only extract NEW information not already in the Wiki.
- Categorize logically (e.g., Sepsis/Diabetes -> "Diseases/Issues", Sodium/Creatinine -> "Labs/Blood Work").
- Be specific and actionable.
- If no new information is found, return empty lists for both keys.
- Do not include patient-specific data; extract the general rule behind the decision.
- Attributes are optional; only include them if they can be inferred from the workflow."""

    def format_prompt(self, context: dict) -> str:
        outputs_text = "\n\n".join(
            f"=== {step.upper().replace('_', ' ')} ===\n{content}"
            for step, content in context.get("workflow_outputs", {}).items()
        )
        return f"""Current Doctor's Wiki:
{context.get("wiki", "No wiki loaded.")}

--- COMPLETED WORKFLOW OUTPUTS ---

{outputs_text}

---

Identify any new clinical protocols or physician preferences to extract, including appropriate categories."""

    def extract_updates(
        self,
        wiki_content: str,
        outputs: dict,
    ) -> tuple[AgentOutput, dict]:
        """
        Runs extraction and returns (AgentOutput, parsed_updates_dict).
        """
        context = {
            "wiki": wiki_content,
            "workflow_outputs": outputs,
        }
        output = self.run(context, wiki=wiki_content)

        try:
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
            
            # Ensure required keys exist
            if "new_protocols" not in parsed: parsed["new_protocols"] = []
            if "new_preferences" not in parsed: parsed["new_preferences"] = []

        except (json.JSONDecodeError, IndexError, ValueError):
            parsed = {
                "new_protocols": [],
                "new_preferences": [],
            }

        return output, parsed
