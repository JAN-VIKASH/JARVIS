"""
Faster-Whisper Speech-to-Text provider implementation.
"""
import numpy as np
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from voice.base_stt import BaseSTT
from voice.config import voice_settings
from voice.logger import voice_logger

class FasterWhisperSTT(BaseSTT):
    """
    STT provider using the faster-whisper package.
    """
    def __init__(self):
        # Import inside __init__ to speed up startup times if voice is disabled
        from faster_whisper import WhisperModel
        
        voice_logger.info(f"Initializing FasterWhisperSTT with model: {voice_settings.STT_MODEL}")
        
        # Enforce local files only to prevent downloading during startup
        try:
            self.model = WhisperModel(
                voice_settings.STT_MODEL,
                device="cpu",
                compute_type="int8",
                local_files_only=True
            )
        except Exception as e:
            voice_logger.error(
                f"Failed to load Whisper model '{voice_settings.STT_MODEL}' offline. "
                "Please run 'python voice/download_models.py' first to download required models.\n"
                f"Error details: {e}"
            )
            raise RuntimeError(
                f"Whisper model '{voice_settings.STT_MODEL}' is not pre-downloaded. Run the downloader utility."
            ) from e
            
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def transcribe(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """
        Transcribe the audio array into text using a thread pool to avoid blocking the event loop.
        """
        if audio_data is None or len(audio_data) == 0:
            return ""
            
        # Run synchronous transcription in a background thread
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            self.executor,
            self._transcribe_sync,
            audio_data,
            sample_rate
        )
        return text

    def _transcribe_sync(self, audio_data: np.ndarray, sample_rate: int) -> str:
        # faster-whisper expects float32 audio normalized between -1.0 and 1.0
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0
            
        segments, info = self.model.transcribe(audio_data, beam_size=5)
        text_segments = [segment.text for segment in segments]
        full_text = " ".join(text_segments).strip()
        return full_text
