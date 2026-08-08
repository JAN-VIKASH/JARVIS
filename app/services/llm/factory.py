"""
LLM Provider Factory.
"""

from app.services.llm.base import BaseLLM
from app.services.llm.placeholder import PlaceholderLLM
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.groq_provider import GroqProvider
from app.config.settings import settings
from app.core.exceptions import ConfigurationError

class LLMProviderFactory:
    """
    Factory class to instantiate LLM providers.
    """
    @staticmethod
    def get_provider(provider_name: str) -> BaseLLM:
        name = provider_name.lower().strip()
        if name == "placeholder":
            return PlaceholderLLM()
        elif name == "openai":
            return OpenAIProvider()
        elif name == "groq":
            return GroqProvider()
        # Future providers (e.g. claude, gemini, ollama) can be added here
        else:
            raise ConfigurationError(f"Unsupported LLM provider: {provider_name}")
