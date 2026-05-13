"""
PatientContext — the running patient context layer.

Persists across workflow runs (Admit → Review → Discharge) as a JSON file
in context/records/{patient_id}.json. Each completed workflow appends a
WorkflowRecord distilled by the ContextSynthesisAgent.

The key invariant: subsequent workflows receive a structured problem list,
not raw output dumps. This keeps prompt sizes bounded while ensuring agents
know what prior teams flagged.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

_RECORDS_DIR = Path(__file__).parent / "records"


@dataclass
class WorkflowRecord:
    """
    Structured summary of one completed workflow.
    Written by ContextSynthesisAgent, not by hand.
    """
    workflow: str               # "admission" | "case_management" | "discharge"
    timestamp: str              # ISO 8601 — when the workflow completed
    summary: str                # 2–3 sentence synthesis of what happened
    key_findings: list[str] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)
    resolved_issues: list[str] = field(default_factory=list)


@dataclass
class PatientContext:
    """
    The running patient context for a single patient across their care episode.

    Loaded at the start of each workflow run, updated at the end.
    Injected into the agent system context so every agent in a subsequent
    workflow knows what prior teams found and flagged.
    """
    patient_id: str
    workflow_history: list[WorkflowRecord] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    @property
    def active_issues(self) -> list[str]:
        """
        Cross-workflow running problem list.
        Items are open until a later workflow explicitly marks them resolved.
        """
        resolved: set[str] = set()
        open_items: list[str] = []
        for record in self.workflow_history:
            resolved.update(record.resolved_issues)
            open_items.extend(record.open_issues)
        return [i for i in open_items if i not in resolved]

    @property
    def last_workflow(self) -> str:
        if not self.workflow_history:
            return ""
        return self.workflow_history[-1].workflow

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_record(self, record: WorkflowRecord) -> None:
        self.workflow_history.append(record)

    # ------------------------------------------------------------------
    # Prompt injection
    # ------------------------------------------------------------------

    def to_prompt_str(self) -> str:
        """
        Formats the patient history for injection into agent system context.
        Every agent in a subsequent workflow sees this before its own instructions.
        """
        if not self.workflow_history:
            return ""

        lines = ["## Prior Clinical Context for This Patient\n"]

        for rec in self.workflow_history:
            date = rec.timestamp[:10]
            lines.append(f"### {rec.workflow.replace('_', ' ').title()} ({date})")
            lines.append(rec.summary)

            if rec.key_findings:
                lines.append("\n**Key findings:**")
                for f in rec.key_findings:
                    lines.append(f"- {f}")

            if rec.open_issues:
                lines.append("\n**Open issues:**")
                for i in rec.open_issues:
                    lines.append(f"- ⚠ {i}")

            if rec.resolved_issues:
                lines.append("\n**Resolved this workflow:**")
                for r in rec.resolved_issues:
                    lines.append(f"- ✓ {r}")

            lines.append("")

        active = self.active_issues
        if active:
            lines.append("### Active Problem List (carry forward into this workflow)")
            for issue in active:
                lines.append(f"- ⚠ {issue}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        _RECORDS_DIR.mkdir(exist_ok=True)
        path = _RECORDS_DIR / f"{self.patient_id}.json"
        path.write_text(json.dumps(self._to_dict(), indent=2))

    @classmethod
    def load(cls, patient_id: str) -> "PatientContext":
        """Loads existing context or returns a fresh one if none exists yet."""
        path = _RECORDS_DIR / f"{patient_id}.json"
        if not path.exists():
            return cls(patient_id=patient_id)
        data = json.loads(path.read_text())
        records = [WorkflowRecord(**r) for r in data.get("workflow_history", [])]
        return cls(patient_id=data["patient_id"], workflow_history=records)

    @classmethod
    def clear(cls, patient_id: str) -> None:
        """Resets context for a patient — useful for demos and testing."""
        path = _RECORDS_DIR / f"{patient_id}.json"
        if path.exists():
            path.unlink()

    def _to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "workflow_history": [
                {
                    "workflow": r.workflow,
                    "timestamp": r.timestamp,
                    "summary": r.summary,
                    "key_findings": r.key_findings,
                    "open_issues": r.open_issues,
                    "resolved_issues": r.resolved_issues,
                }
                for r in self.workflow_history
            ],
        }
