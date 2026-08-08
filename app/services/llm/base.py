"""
Base LLM interface class.
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from app.models.chat_models import ChatRequest, LLMResult

from app.services.llm.generation_config import GenerationConfig

class BaseLLM(ABC):
    """
    Abstract Base Class for LLM providers.
    All future providers (OpenAI, Claude, Gemini, etc.) must implement this interface.
    """
    
    @abstractmethod
    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        """
        Generate a response based on the input request, system prompt, and optional history.
        """
        pass

