"""
DriftAgent — identifies "drift" between the physician's wiki and
updated clinical evidence or institutional protocols.
"""

import json
import re
from agents.base import BaseAgent, AgentOutput
from wiki.loader import get_wiki_file_content


class DriftAgent(BaseAgent):
    """
    Scans the Doctor's Wiki and compares it against updated evidence.
    Generates warnings for rules that may be outdated or conflicting.
    """

    @property
    def name(self) -> str:
        return "drift_detection"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical safety auditor. Your job is to compare a physician's personalized reasoning wiki against newly available clinical guidelines and evidence.

Identify "drift" — cases where the physician's stored protocols or notes may now conflict with updated evidence or where a new guideline suggests a change in practice.

For each conflict found, provide:
1. The Wiki Rule ID and text.
2. The updated evidence/guideline it conflicts with.
3. A brief explanation of the risk or change.
4. A prompt for the physician to review.

Output format:
## Wiki Drift Report

🚩 [ID: xxxxxx] [Rule Text]
- **Conflict:** [Description of conflict with new evidence]
- **Evidence:** [Citation of new guideline/study]
- **Action:** [Prompt for physician review]

If no drift is detected, state: "No clinical drift detected." """

    def format_prompt(self, context: dict) -> str:
        # Load institutional guidelines if not provided
        updated_evidence = context.get("updated_evidence")
        if not updated_evidence:
            updated_evidence = get_wiki_file_content("default", "guidelines.md")

        return f"""Current Doctor's Wiki:
{context.get("wiki", "No wiki loaded.")}

--- UPDATED CLINICAL EVIDENCE / GUIDELINES ---

{updated_evidence}

---

Please identify any drift or conflicts between the physician's reasoning and the updated evidence."""
