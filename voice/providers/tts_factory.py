"""
Factory for resolving TTS engines.
"""
from voice.base_tts import BaseTTS
from voice.config import voice_settings
from voice.providers.piper_provider import PiperTTS

class TTSProviderFactory:
    """
    TTS Provider Factory to resolve the active Text-to-Speech provider.
    """
    @staticmethod
    def get_provider(provider_name: str = None) -> BaseTTS:
        name = (provider_name or voice_settings.TTS_PROVIDER).lower().strip()
        if name == "piper":
            return PiperTTS()
        # Future providers (elevenlabs, openai_tts, azure, edge_tts) can be resolved here
        else:
            raise ValueError(f"Unsupported TTS provider: {name}")
