"""
Central factory to resolve backend services.
"""
from app.services.interfaces.base_chat_service import BaseChatService
from app.services.chat_service import ChatService
from app.services.llm.base import BaseLLM
from app.core.dependencies import get_llm, get_memory
from memory.base import BaseMemory

class ServiceFactory:
    """
    Factory to instantiate/resolve backend core services.
    Ensures decoupled dependencies and enables clean DI.
    """
    @staticmethod
    def get_chat_service() -> BaseChatService:
        """
        Resolves and returns a BaseChatService instance.
        """
        return ChatService()

    @staticmethod
    def get_llm() -> BaseLLM:
        """
        Resolves and returns the active BaseLLM provider.
        """
        return get_llm()

    @staticmethod
    def get_memory() -> BaseMemory:
        """
        Resolves and returns the active BaseMemory provider.
        """
        return get_memory()

    @staticmethod
    def get_memory_service():
        """
        Resolves and returns the active long-term MemoryService instance.
        """
        from memory.memory_factory import MemoryFactory
        return MemoryFactory.get_memory_service()
