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
        user_prompt: str
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
