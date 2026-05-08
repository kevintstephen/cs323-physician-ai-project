from google import genai
from google.genai import types
from .base import LLMBackend, LLMResponse

class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def generate(
        self, 
        model: str, 
        system_prompt: str, 
        wiki: str, 
        user_prompt: str
    ) -> LLMResponse:
        # Prepend the wiki to the system prompt to create a stable prefix
        # This is better for LLM reasoning and potential context caching
        full_system_prompt = ""
        if wiki:
            full_system_prompt += f"## Doctor's Wiki\n\n{wiki}\n\n"
        full_system_prompt += system_prompt
            
        config = types.GenerateContentConfig(
            system_instruction=full_system_prompt,
            max_output_tokens=2048,
        )
        
        response = self.client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config
        )
        
        usage = response.usage_metadata
        
        return LLMResponse(
            content=response.text,
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=usage.candidates_token_count or 0,
            cache_read_tokens=usage.cached_content_token_count or 0,
        )
