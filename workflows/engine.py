import json
from dataclasses import dataclass, field
from typing import Optional, Type

import anthropic

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

    def __init__(self, client: anthropic.Anthropic, wiki: str = ""):
        self.client = client
        self.wiki = wiki

    def run(self, steps: list[WorkflowStep], session: PatientSession) -> WorkflowState:
        state = WorkflowState(session=session)

        for step in steps:
            print(f"  → running {step.name}...")
            agent = step.agent_class(self.client)
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
        Always includes the raw patient data; optionally includes prior step outputs.
        """
        context: dict = {
            "patient_id": session.patient_id,
            "patient_data": session.patient_data,
            "prior_history": session.prior_history,
            "ed_notes": session.ed_notes,
            "handoff_notes": session.handoff_notes,
        }
        for key in step.context_keys:
            if key in state.outputs:
                context[key] = state.outputs[key]
        return context
