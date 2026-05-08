from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

class LLMBackend(ABC):
    """
    Abstract base class for LLM providers.
    """
    
    @abstractmethod
    def generate(
        self, 
        model: str, 
        system_prompt: str, 
        wiki: str, 
        user_prompt: str
    ) -> LLMResponse:
        """
        Generates a response from the LLM.
        """
        pass
