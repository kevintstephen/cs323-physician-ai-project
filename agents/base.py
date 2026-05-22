from abc import ABC, abstractmethod
from dataclasses import dataclass

from llm.base import LLMBackend, LLMResponse


@dataclass
class AgentOutput:
    agent_name: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class BaseAgent(ABC):
    """
    Every agent in the system extends this class.

    Subclasses must define:
      - name: a short identifier used as the workflow step key
      - system_prompt: the role/persona/instructions for this agent
      - format_prompt(): how to turn the workflow context into a user message

    The base class handles the LLM backend call.
    """

    def __init__(self, backend: LLMBackend, model: str):
        self.backend = backend
        self.model = model

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        pass

    @abstractmethod
    def format_prompt(self, context: dict) -> str:
        """Build the user-turn message from the workflow context dict."""
        pass

    def run(self, context: dict, wiki: str = "") -> AgentOutput:
        # Ground every agent in the requirement to cite the wiki
        grounded_system_prompt = self.system_prompt
        if wiki:
            grounded_system_prompt += (
                "\n\n## Grounding Requirement\n"
                "When making clinical recommendations, drafting notes, or identifying action items, "
                "you MUST explicitly cite the Doctor's Wiki if a relevant protocol or preference exists. "
                "Use the format `[WikiID: XXXXXX]` where XXXXXX is the ID provided in the Wiki text. "
                "If multiple rules apply, cite them all."
            )

        response = self.backend.generate(
            model=self.model,
            system_prompt=grounded_system_prompt,
            wiki=wiki,
            user_prompt=self.format_prompt(context)
        )

        return AgentOutput(
            agent_name=self.name,
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
        )
