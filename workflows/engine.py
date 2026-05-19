from dataclasses import dataclass, field
from typing import Optional, Type

from llm.base import LLMBackend
from agents.base import BaseAgent
from context.session import PatientSession, WorkflowState


@dataclass
class WorkflowStep:
    """
    Declares one step in a workflow DAG.

    name:         Key used to store this step's output in WorkflowState.outputs.
    agent_class:  The BaseAgent subclass to instantiate for this step.
    context_keys: Which prior step outputs to include in this agent's context.
                  If empty, only the raw patient session data is passed.
    parallel_group: Steps sharing the same group number may run concurrently.
                  (Reserved for future parallelism — engine currently runs sequentially.)
    """

    name: str
    agent_class: Type[BaseAgent]
    context_keys: list[str] = field(default_factory=list)
    parallel_group: Optional[int] = None


class WorkflowEngine:
    """
    Executes a list of WorkflowSteps against a PatientSession.

    Adding a new workflow = define a list of WorkflowSteps elsewhere and
    call engine.run(steps, session). The engine never needs to change.
    """

    def __init__(self, backend: LLMBackend, model: str, wiki: str = ""):
        self.backend = backend
        self.model = model
        self.wiki = wiki

    def run_steps(
        self,
        steps: list[WorkflowStep],
        session: PatientSession,
        patient_context=None,
        workflow_name: str = "",
        doctor_id: str = "default",
    ):
        """
        Generator that yields (step_name, output, state) after each step completes.
        Use for streaming UIs — the caller can update progress after every step.
        run() remains for CLI/batch use and is unchanged.

        patient_context: optional PatientContext. When provided:
          - Prior context is injected into every agent's system prompt so
            agents know what previous workflows found and flagged.
          - After all steps complete, ContextSynthesisAgent distills the
            outputs into a WorkflowRecord and saves it to the context.
        workflow_name: used to label the WorkflowRecord (e.g. "admission").
        doctor_id: used to identify which wiki to update.
        """
        from datetime import datetime, timezone
        from context.patient_context import WorkflowRecord
        from agents.context_synthesis import ContextSynthesisAgent
        from agents.wiki_substrate import WikiSubstrateAgent
        from wiki.loader import update_wiki

        # Build effective wiki: patient context first (most recent history),
        # then the stable doctor wiki. Patient context changes per run so it
        # sits outside the doctor-wiki cache block.
        effective_wiki = self.wiki
        if patient_context:
            context_str = patient_context.to_prompt_str()
            if context_str:
                effective_wiki = (
                    context_str + ("\n\n---\n\n" + self.wiki if self.wiki else "")
                )

        state = WorkflowState(session=session)

        for step in steps:
            agent = step.agent_class(self.backend, self.model)
            context = self._build_context(step, session, state)
            output = agent.run(context, effective_wiki)
            state.outputs[step.name] = output.content
            yield step.name, output, state

        # After all workflow steps complete, synthesize and persist context.
        if patient_context is not None:
            synthesizer = ContextSynthesisAgent(self.backend, self.model)
            synth_output, parsed = synthesizer.synthesize(
                patient_id=session.patient_id,
                workflow_name=workflow_name or "workflow",
                outputs=state.outputs,
            )

            record = WorkflowRecord(
                workflow=workflow_name or "workflow",
                timestamp=datetime.now(timezone.utc).isoformat(),
                summary=parsed.get("summary", ""),
                key_findings=parsed.get("key_findings", []),
                open_issues=parsed.get("open_issues", []),
                resolved_issues=parsed.get("resolved_issues", []),
            )
            patient_context.add_record(record)
            patient_context.save()

            # Yield synthesis as a named step so the UI can show it
            state.outputs["context_synthesis"] = synth_output.content
            yield "context_synthesis", synth_output, state

            # --- Wiki Evolution (Substrate) ---
            substrate = WikiSubstrateAgent(self.backend, self.model)
            sub_output, updates = substrate.extract_updates(
                wiki_content=self.wiki,
                outputs=state.outputs
            )
            
            # Stage updates for physician review instead of auto-applying
            from wiki.loader import add_pending_updates
            add_pending_updates(
                doctor_id=doctor_id,
                updates=updates
            )

            state.outputs["wiki_substrate"] = sub_output.content
            yield "wiki_substrate", sub_output, state

        state.status = "complete"

    def run(self, steps: list[WorkflowStep], session: PatientSession) -> WorkflowState:
        state = WorkflowState(session=session)

        for step in steps:
            print(f"  → running {step.name}...")
            agent = step.agent_class(self.backend, self.model)
            context = self._build_context(step, session, state)
            output = agent.run(context, self.wiki)
            state.outputs[step.name] = output.content
            cache_info = f" (cache hit: {output.cache_read_tokens} tokens)" if output.cache_read_tokens else ""
            print(f"    ✓ {step.name} complete{cache_info}")

        state.status = "complete"
        return state

    def _build_context(
        self, step: WorkflowStep, session: PatientSession, state: WorkflowState
    ) -> dict:
        """
        Builds the context dict passed to agent.format_prompt().
        Always includes the base patient fields; adds discharge-specific fields
        when a DischargeSession is passed (checked via getattr — no hard import).
        """
        context: dict = {
            "patient_id": session.patient_id,
            "patient_data": session.patient_data,
            "prior_history": session.prior_history,
            "ed_notes": session.ed_notes,
            "handoff_notes": session.handoff_notes,
        }

        # Discharge-specific fields — present only on DischargeSession.
        # Using getattr keeps the engine decoupled from the session subclass.
        _discharge_fields = [
            "admission_date", "discharge_date", "length_of_stay_days",
            "admitting_diagnosis", "discharge_diagnosis", "discharge_disposition",
            "progress_notes", "consult_notes", "procedure_notes",
            "lab_trends", "imaging_reports",
            "admission_medications", "discharge_medications",
            "vitals_trend", "pending_follow_ups",
            "insurance", "primary_care_provider",
            "social_support", "functional_status_at_discharge",
        ]
        for field in _discharge_fields:
            value = getattr(session, field, None)
            if value is not None:
                context[field] = value

        # Prior step outputs
        for key in step.context_keys:
            if key in state.outputs:
                context[key] = state.outputs[key]

        return context
