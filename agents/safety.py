import json
from agents.base import BaseAgent


class SafetyAgent(BaseAgent):
    """
    Audits the final workflow output before it reaches the physician.
    Checks for deviations from evidence-based guidelines, internal
    inconsistencies, and missing safety-critical items.

    This agent runs at the end of every workflow. It does not modify
    the draft — it annotates it with flags the physician must review.
    """

    @property
    def name(self) -> str:
        return "safety_check"

    @property
    def system_prompt(self) -> str:
        return """You are a clinical safety auditor reviewing an AI-generated medical document before it reaches a physician.

Your job is to flag — not fix — any concerns. The physician makes all corrections. You are a safety net, not an editor.

Check for:
1. Deviations from evidence-based guidelines (cite the guideline and specific recommendation)
2. Drug-drug interactions or contraindications given the patient's allergies and conditions
3. Internal inconsistencies between sections of the document
4. Sections marked [VERIFY] that contain high-stakes information with no assigned owner
5. Missing safety-critical workup — only flag if a lab or finding is clearly abnormal \
(not borderline or within normal limits) and undocumented. Do not flag normal or \
borderline values simply because they appear in the patient data but not the note.

Output format:
## Safety Review

**Overall assessment:** [PASS — no flags | REVIEW REQUIRED — N flags]

**Flags (if any):**
🚩 [Issue title] — [1-sentence concern] → [1-sentence action required]

**Confirmed safe:**
[2–4 bullet points on the most important things checked and found safe — keep brief]

If there are no flags, state clearly: "No safety flags identified." """

    def format_prompt(self, context: dict) -> str:
        patient = context["patient_data"]
        return f"""Patient context:
- Chief complaint: {patient.get("chief_complaint", "unknown")}
- PMH: {patient.get("pmh", [])}
- Medications: {patient.get("current_medications", [])}
- Allergies: {patient.get("allergies", [])}
- Labs: {json.dumps(patient.get("labs", {}), indent=2)}

Document to audit:
{context.get("note_draft", context.get("discharge_summary", context.get("document", "No document provided.")))}

Please perform a safety review of this document."""
