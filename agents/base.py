import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import anthropic


DEFAULT_MODEL = os.getenv("MODEL", "claude-opus-4-7")


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

    The base class handles the Anthropic API call with prompt caching:
      - The system prompt is cached (stable across calls)
      - The doctor's wiki is cached (stable within a session)
      - Only the patient-specific user message is uncached
    """

    model: str = DEFAULT_MODEL

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

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
        system_blocks = [
            {
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if wiki:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"## Doctor's Wiki\n\n{wiki}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_blocks,
            messages=[{"role": "user", "content": self.format_prompt(context)}],
        )

        usage = response.usage
        return AgentOutput(
            agent_name=self.name,
            content=response.content[0].text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        )
