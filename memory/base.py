"""
Base interface class for conversation memory.
"""

from abc import ABC, abstractmethod
from typing import List, Dict

class BaseMemory(ABC):
    """
    Abstract Base Class for session memory providers.
    All future memories (Redis, SQL DB, Vector Memory) must implement this interface.
    """

    @abstractmethod
    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve conversation history for a given session ID.
        Returns a list of dicts with role and content keys.
        """
        pass

    @abstractmethod
    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        Append a message to the conversation history for a given session ID.
        """
        pass

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """
        Clear conversation history for a given session ID.
        """
        pass
