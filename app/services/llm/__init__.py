"""
LLM Services module.
"""

from app.services.llm.base import BaseLLM
from app.services.llm.factory import LLMProviderFactory
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.groq_provider import GroqProvider
from app.config.settings import settings

def get_llm_service() -> BaseLLM:
    """
    Factory function to retrieve the configured LLM provider instance.
    """
    return LLMProviderFactory.get_provider(settings.LLM_PROVIDER)

