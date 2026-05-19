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

The Wiki has two main sections:
1. Clinical Protocols: How to manage specific conditions (e.g., "HF exacerbation", "Hyponatremia").
2. Doctor Preferences: General workflow, documentation, or communication styles (e.g., "Communication style", "Consultant communication").

Compare the current workflow (especially the physician's final notes and decisions) against the existing Wiki. Look for:
- Specific thresholds used (e.g., "Always check BMP if Cr > 2.0").
- Repeating patterns in management.
- Formatting or communication styles used consistently.

Output ONLY valid JSON with this exact structure — no preamble, no markdown fences:

{
  "new_protocols": {
    "Condition Name": ["Protocol rule 1", "Protocol rule 2"]
  },
  "new_preferences": {
    "Category Name": ["Preference 1", "Preference 2"]
  }
}

Rules:
- Only extract NEW information not already in the Wiki.
- Be specific and actionable.
- If no new information is found, return empty objects for both keys.
- Do not include patient-specific data; extract the general rule behind the decision."""

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

Identify any new clinical protocols or physician preferences to extract."""

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
            if "new_protocols" not in parsed: parsed["new_protocols"] = {}
            if "new_preferences" not in parsed: parsed["new_preferences"] = {}

        except (json.JSONDecodeError, IndexError, ValueError):
            parsed = {
                "new_protocols": {},
                "new_preferences": {},
            }

        return output, parsed
