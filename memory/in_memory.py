"""
Thread-safe in-memory conversation memory implementation.
"""

from typing import List, Dict
from collections import deque
import asyncio
from memory.base import BaseMemory

class InMemoryMemory(BaseMemory):
    """
    In-memory session memory provider.
    Limits history to the last 10 exchanges (20 total messages).
    """
    def __init__(self, limit: int = 20):
        self.limit = limit
        # Dictionary mapping session_id -> deque of message dicts
        self._storage: Dict[str, deque] = {}
        self._lock = asyncio.Lock()

    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        async with self._lock:
            if session_id not in self._storage:
                return []
            return list(self._storage[session_id])

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        async with self._lock:
            if session_id not in self._storage:
                self._storage[session_id] = deque(maxlen=self.limit)
            self._storage[session_id].append({"role": role, "content": content})

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._storage:
                self._storage[session_id].clear()
