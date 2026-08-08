"""
Factory for resolving STT engines.
"""
from voice.base_stt import BaseSTT
from voice.config import voice_settings
from voice.providers.stt_provider import FasterWhisperSTT

class STTProviderFactory:
    """
    STT Provider Factory to resolve the active Speech-to-Text provider.
    """
    @staticmethod
    def get_provider(provider_name: str = None) -> BaseSTT:
        name = (provider_name or voice_settings.STT_PROVIDER).lower().strip()
        if name == "faster_whisper":
            return FasterWhisperSTT()
        # Future providers (openai_whisper, deepgram, etc.) can be resolved here
        else:
            raise ValueError(f"Unsupported STT provider: {name}")
