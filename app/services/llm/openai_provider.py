"""
OpenAI LLM provider implementation using the Responses API.
"""

from typing import List, Dict, Optional, Any
import time
import asyncio
import logging
from openai import AsyncOpenAI, APIError, AuthenticationError, RateLimitError, APITimeoutError
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.models.chat_models import ChatRequest, LLMResult
from app.config.settings import settings
from app.core.exceptions import LLMServiceError

logger = logging.getLogger("jarvis")

class OpenAIProvider(BaseLLM):
    """
    OpenAI LLM Provider using the modern Responses API.
    """
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured in environment settings.")
        
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.REQUEST_TIMEOUT
        )
        self.model_name = settings.MODEL_NAME
        self.provider_name = "openai"

    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        """
        Generate a response with retry logic and latency profiling.
        """
        input_messages = self._prepare_input(request.message, system_prompt, history)
        
        start_time = time.perf_counter()
        
        # Exponential backoff retry logic for transient API issues
        max_retries = 3
        initial_delay = 1.0
        backoff_factor = 2.0
        
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._execute_request(input_messages, config)
                latency = time.perf_counter() - start_time
                return self._parse_response(response, latency)
            except AuthenticationError as e:
                # Do NOT retry authentication failures
                logger.error(f"OpenAI Authentication Error (No Retry): {e}")
                raise LLMServiceError("OpenAI authentication failed: Please verify your API credentials.")
            except (RateLimitError, APITimeoutError, APIError, OSError) as e:
                last_exception = e
                logger.warning(
                    f"OpenAI transient error on attempt {attempt}/{max_retries}: {e}. "
                    f"Retrying in {initial_delay}s..."
                )
                if attempt == max_retries:
                    break
                await asyncio.sleep(initial_delay)
                initial_delay *= backoff_factor
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI Provider execution: {e}")
                raise LLMServiceError(f"Unexpected error: {str(e)}")
                
        # If we exhausted retries
        latency = time.perf_counter() - start_time
        logger.error(f"OpenAI calls failed after {max_retries} attempts: {last_exception}")
        
        # Specific classification for final exception
        if isinstance(last_exception, RateLimitError):
            raise LLMServiceError("OpenAI rate limit exceeded. Please try again later.")
        elif isinstance(last_exception, APITimeoutError):
            raise LLMServiceError("OpenAI request timed out.")
        else:
            raise LLMServiceError(f"OpenAI API call failed: {str(last_exception)}")

    def _prepare_input(self, message: str, system_prompt: str, history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        """
        Prepares the list of messages, merging system prompt, history, and the latest user query.
        """
        messages = []
        # Add system prompt as a system instruction
        messages.append({"role": "system", "content": system_prompt})
        
        # Append history if present
        if history:
            for exchange in history:
                messages.append({"role": exchange["role"], "content": exchange["content"]})
                
        # Append user message
        messages.append({"role": "user", "content": message})
        return messages

    async def _execute_request(self, input_messages: List[Dict[str, str]], config: Optional[GenerationConfig] = None) -> Any:
        """
        Executes the network call to the OpenAI API using the modern Responses API.
        Separated out to allow custom streaming implementations later.
        """
        kwargs = {
            "model": self.model_name,
            "input": input_messages
        }
        # Note: Since the prompt says "providers should map only the parameters they support and silently ignore unsupported parameters"
        # We can map temperature, max_tokens, seed, stop, etc. if they are supported by OpenAI responses.create
        if config:
            if config.temperature is not None:
                kwargs["temperature"] = config.temperature
            if config.max_tokens is not None:
                kwargs["max_tokens"] = config.max_tokens
            if config.top_p is not None:
                kwargs["top_p"] = config.top_p
            if config.stop is not None:
                kwargs["stop"] = config.stop
            if hasattr(config, "seed") and config.seed is not None:
                kwargs["seed"] = config.seed
                
        return await self.client.responses.create(**kwargs)

    def _parse_response(self, response: Any, latency: float) -> LLMResult:
        """
        Parses the raw response object from client.responses.create into LLMResult.
        """
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise LLMServiceError("OpenAI Responses API returned an empty output.")

        # Capture tokens if available
        input_tokens = None
        output_tokens = None
        total_tokens = None
        
        usage = getattr(response, "usage", None)
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)

        return LLMResult(
            response=output_text,
            provider=self.provider_name,
            model=self.model_name,
            latency=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )
