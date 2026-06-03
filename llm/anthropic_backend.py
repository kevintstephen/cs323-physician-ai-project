from typing import Callable

import anthropic
from .base import LLMBackend, LLMResponse


class AnthropicBackend(LLMBackend):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(
        self,
        model: str,
        system_prompt: str,
        wiki: str,
        user_prompt: str,
    ) -> LLMResponse:
        system_blocks = []
        
        # Put the stable wiki first so it can be shared across all agents in a workflow
        if wiki:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"## Doctor's Wiki\n\n{wiki}",
                    "cache_control": {"type": "ephemeral"},
                }
            )
            
        # Then add the agent-specific instructions
        system_blocks.append(
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        )

        response = self.client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
        )

        usage = response.usage
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        )

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
        Proper Anthropic tool-use loop.

        Runs until the model stops requesting tool calls (stop_reason != "tool_use").
        Accumulates token counts across all turns so callers get accurate usage.
        """
        system_blocks = []
        if wiki:
            system_blocks.append({
                "type": "text",
                "text": f"## Doctor's Wiki\n\n{wiki}",
                "cache_control": {"type": "ephemeral"},
            })
        system_blocks.append({
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        })

        messages = [{"role": "user", "content": user_prompt}]
        total_input = total_output = total_cache = 0

        while True:
            response = self.client.messages.create(
                model=model,
                # The prescription agent emits a JSON array of full order objects, which
                # routinely runs past 4096 tokens for multi-drug admissions and gets cut
                # off mid-object — leaving unparseable JSON. Give the final turn room to
                # complete the array.
                max_tokens=16384,
                system=system_blocks,
                tools=tools,
                messages=messages,
            )

            usage = response.usage
            total_input  += usage.input_tokens
            total_output += usage.output_tokens
            total_cache  += getattr(usage, "cache_read_input_tokens", 0)

            if response.stop_reason == "tool_use":
                # Execute every tool call the model requested this turn
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = tool_executor(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Append assistant turn + tool results before next iteration
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Model is done — extract final text response
                text = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
                return LLMResponse(
                    content=text,
                    input_tokens=total_input,
                    output_tokens=total_output,
                    cache_read_tokens=total_cache,
                )
