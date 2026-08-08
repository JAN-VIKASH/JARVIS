"""
Abstract base class for Speech-to-Text providers.
"""
from abc import ABC, abstractmethod
import numpy as np

class BaseSTT(ABC):
    """
    Abstract interface for STT engines.
    """
    @abstractmethod
    async def transcribe(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """
        Transcribe audio samples into text.
        """
        pass
