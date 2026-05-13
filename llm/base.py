import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class LLMBackend(ABC):
    """
    Abstract base class for LLM providers.

    generate()            — standard single-turn call (all agents use this)
    generate_with_tools() — agentic tool-use loop; overridden by backends that
                            support native function calling (AnthropicBackend).
                            The default implementation is a two-pass prompt fallback
                            so any backend can support tools without native API support.
    """

    @abstractmethod
    def generate(
        self,
        model: str,
        system_prompt: str,
        wiki: str,
        user_prompt: str,
    ) -> LLMResponse:
        pass

    def generate_with_tools(
        self,
        model: str,
        system_prompt: str,
        wiki: str,
        user_prompt: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict], str],
    ) -> LLMResponse:
        """
        Default two-pass fallback for backends without native function calling.

        Pass 1: Ask the model which tools to call (returns JSON).
        Pass 2: Execute the tools, inject results, ask for the final answer.

        Backends with native tool support (e.g. AnthropicBackend) override this
        with a proper agentic loop.
        """
        # Describe available tools in the system prompt
        tool_descriptions = "\n\n".join(
            f"Tool: {t['name']}\n"
            f"Description: {t['description']}\n"
            f"Parameters: {json.dumps(t['input_schema'].get('properties', {}))}"
            for t in tools
        )
        tool_names = [t["name"] for t in tools]

        planning_prompt = (
            f"{user_prompt}\n\n"
            f"Available tools: {', '.join(tool_names)}\n\n"
            "Before writing your final answer, list every tool call you need to make "
            "as a JSON array:\n"
            '[{"name": "tool_name", "args": {"param": "value"}}, ...]\n\n'
            "Wrap the array in <tool_calls>...</tool_calls> tags. "
            "If no tools are needed, write <tool_calls>[]</tool_calls>."
        )

        planning_system = (
            system_prompt
            + f"\n\n## Available Tools\n\n{tool_descriptions}"
        )

        # Pass 1 — get tool calls
        pass1 = self.generate(model, planning_system, wiki, planning_prompt)

        # Extract and execute tool calls
        match = re.search(r"<tool_calls>(.*?)</tool_calls>", pass1.content, re.DOTALL)
        tool_results_text = ""
        if match:
            try:
                calls = json.loads(match.group(1).strip())
                results = []
                for call in calls:
                    result = tool_executor(call["name"], call.get("args", {}))
                    results.append(f"[{call['name']}] → {result}")
                tool_results_text = "\n".join(results)
            except (json.JSONDecodeError, KeyError):
                pass

        # Pass 2 — final answer with tool results injected
        final_prompt = (
            f"{user_prompt}\n\n"
            + (f"## Tool Results\n\n{tool_results_text}\n\n" if tool_results_text else "")
            + "Now produce your final answer."
        )
        pass2 = self.generate(model, system_prompt, wiki, final_prompt)

        return LLMResponse(
            content=pass2.content,
            input_tokens=pass1.input_tokens + pass2.input_tokens,
            output_tokens=pass1.output_tokens + pass2.output_tokens,
            cache_read_tokens=pass1.cache_read_tokens + pass2.cache_read_tokens,
        )
