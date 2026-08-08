"""
FastAPI dependencies injection setup.
"""

from fastapi import Depends
from app.services.llm.base import BaseLLM
from app.services.llm import get_llm_service
from app.config.prompts import prompt_config
from memory.base import BaseMemory
from memory.in_memory import InMemoryMemory

# Global memory instance (will act as singleton for current process)
_memory_instance = InMemoryMemory()

def get_llm() -> BaseLLM:
    """
    Dependency injection provider for the LLM service.
    """
    return get_llm_service()

def get_system_prompt() -> str:
    """
    Dependency injection provider for the loaded system prompt.
    """
    return prompt_config.get_system_prompt()

def get_memory() -> BaseMemory:
    """
    Dependency injection provider for conversation history memory.
    """
    return _memory_instance

