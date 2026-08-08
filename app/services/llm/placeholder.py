"""
Placeholder LLM service implementation.
"""

from typing import List, Dict, Optional
import time
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest, LLMResult
import logging

logger = logging.getLogger("jarvis")

from app.services.llm.generation_config import GenerationConfig

class PlaceholderLLM(BaseLLM):
    """
    Dummy LLM provider for Phase 1 and local development testing.
    """
    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        start_time = time.perf_counter()
        logger.debug(f"Placeholder LLM processing message: '{request.message}'")
        
        latency = time.perf_counter() - start_time
        return LLMResult(
            response="Hello, I am Jarvis.",
            provider="placeholder",
            model="mock-model",
            latency=latency,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15
        )

