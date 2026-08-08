"""
Voice configuration settings.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class VoiceSettings(BaseSettings):
    """
    Voice Interface configurations loaded from environment variables and .env file.
    """
    WAKE_WORD: str = "Hey Jarvis"
    WAKE_WORD_MODEL_PATH: str = "voice/models/hey_jarvis_v0.1.onnx"
    WAKE_WORD_THRESHOLD: float = 0.5
    WAKE_WORD_ENABLED: bool = False
    VOICE_NAME: str = "en_US-lessac-medium"
    VOICE_ENABLED: bool = True
    STT_PROVIDER: str = "faster_whisper"
    TTS_PROVIDER: str = "piper"
    STT_MODEL: str = "base"
    VOICE_MODELS_DIR: str = "voice/models"
    PIPER_BIN_DIR: str = "voice/bin/piper"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

voice_settings = VoiceSettings()
