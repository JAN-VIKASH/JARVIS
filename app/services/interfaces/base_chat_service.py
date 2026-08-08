"""
Abstract interface for the ChatService.
"""
from abc import ABC, abstractmethod
from app.models.chat_models import ChatRequest

class BaseChatService(ABC):
    """
    Base Chat Service abstraction.
    All ChatService implementations must inherit from this class.
    """
    @abstractmethod
    async def execute_chat(self, request: ChatRequest) -> str:
        """
        Executes a chat session with memory, prompts, and the LLM.
        """
        pass
