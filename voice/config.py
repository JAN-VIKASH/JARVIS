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
