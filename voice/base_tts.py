"""
Abstract base class for Text-to-Speech providers.
"""
from abc import ABC, abstractmethod

class BaseTTS(ABC):
    """
    Abstract interface for TTS engines.
    """
    @abstractmethod
    async def synthesize_and_play(self, text: str) -> None:
        """
        Synthesize text and play audio asynchronously.
        """
        pass
