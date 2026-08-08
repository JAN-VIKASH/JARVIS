"""
Voice Service coordinator managing the speech-to-text, chat, and text-to-speech pipeline.
"""
import time
import asyncio
from voice.base_stt import BaseSTT
from voice.base_tts import BaseTTS
from app.services.interfaces.base_chat_service import BaseChatService
from voice.session import VoiceSession
from voice.microphone import AudioRecorder
from voice.logger import voice_logger
from app.models.chat_models import ChatRequest

class VoiceService:
    """
    Coordinates the audio capture, STT, Chat, and TTS steps.
    Decoupled from specific LLM or provider logic.
    """
    def __init__(self, stt: BaseSTT, tts: BaseTTS, chat_service: BaseChatService, session: VoiceSession = None):
        self.stt = stt
        self.tts = tts
        self.chat_service = chat_service
        self.session = session or VoiceSession()
        self.recorder = AudioRecorder(sample_rate=16000, channels=1)
        self.is_running = False

    async def start(self) -> None:
        """
        Start the voice service pipeline.
        """
        self.is_running = True
        self.session.set_idle()
        try:
            from app.services.factory import ServiceFactory
            memory_service = ServiceFactory.get_memory_service()
            memory_service.start()
        except Exception as e:
            voice_logger.error(f"Failed to start memory service background loop in voice: {e}")
        voice_logger.info("VoiceService started.")

    async def stop(self) -> None:
        """
        Stop the voice service pipeline and clean up microphone resources.
        """
        self.is_running = False
        self.recorder.close()
        self.session.set_idle()
        try:
            from app.services.factory import ServiceFactory
            memory_service = ServiceFactory.get_memory_service()
            await memory_service.shutdown()
        except Exception as e:
            voice_logger.error(f"Error shutting down memory service: {e}")
        voice_logger.info("VoiceService stopped.")

    async def trigger_recording_start(self) -> None:
        """
        Start recording from the microphone.
        """
        if not self.is_running:
            raise RuntimeError("VoiceService is not running.")
        self.session.start_recording()
        self.recorder.start_recording()

    async def trigger_recording_stop(self) -> str:
        """
        Stop recording, transcribe audio, call ChatService, and play AI audio response.
        """
        if not self.is_running:
            raise RuntimeError("VoiceService is not running.")
            
        self.session.stop_recording()
        audio_data = self.recorder.stop_recording()
        
        if audio_data is None or len(audio_data) == 0:
            voice_logger.warning("No audio recorded.")
            self.session.set_idle()
            return "No audio recorded."

        # Speech-to-Text transcription
        voice_logger.info("Starting Speech-to-Text transcription...")
        stt_start = time.perf_counter()
        text = await self.stt.transcribe(audio_data, 16000)
        stt_latency = time.perf_counter() - stt_start
        
        voice_logger.info(f"Speech recognized: '{text}' | STT Latency: {stt_latency:.4f}s")
        
        if not text.strip():
            voice_logger.warning("No speech recognized.")
            self.session.set_idle()
            return "No speech recognized."

        # Chat service orchestration
        voice_logger.info("Calling ChatService...")
        chat_start = time.perf_counter()
        request = ChatRequest(message=text, session_id=self.session.session_id, is_voice=True)
        ai_response = await self.chat_service.execute_chat(request)
        chat_latency = time.perf_counter() - chat_start
        
        voice_logger.info(f"AI response generated | Latency: {chat_latency:.4f}s")

        # Text-to-Speech synthesis and playback
        self.session.set_speaking()
        voice_logger.info("Synthesizing AI response to speech...")
        await self.tts.synthesize_and_play(ai_response)
        
        self.session.set_idle()
        return ai_response
