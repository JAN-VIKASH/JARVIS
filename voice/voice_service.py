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

        # Initialize wake-word detector lazily (Phase 10)
        from voice.config import voice_settings
        from voice.wake_word import WakeWordDetector
        self.wake_detector = WakeWordDetector(
            model_path=voice_settings.WAKE_WORD_MODEL_PATH,
            threshold=voice_settings.WAKE_WORD_THRESHOLD
        )
        self.wake_word_task = None
        self.wake_word_running = False

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

        # Start continuous listening loop if wake-word is enabled (Phase 10)
        from voice.config import voice_settings
        if voice_settings.WAKE_WORD_ENABLED:
            await self.start_wake_word_loop()

        voice_logger.info("VoiceService started.")

    async def stop(self) -> None:
        """
        Stop the voice service pipeline and clean up microphone resources.
        """
        self.is_running = False

        # Stop background wake loop (Phase 10)
        await self.stop_wake_word_loop()

        self.recorder.close()
        self.session.set_idle()
        try:
            from app.services.factory import ServiceFactory
            memory_service = ServiceFactory.get_memory_service()
            await memory_service.shutdown()
        except Exception as e:
            voice_logger.error(f"Error shutting down memory service: {e}")
        voice_logger.info("VoiceService stopped.")

    async def start_wake_word_loop(self) -> None:
        """
        Start continuous offline wake word detection in the background.
        """
        from voice.config import voice_settings
        if not self.wake_detector.is_available() or not voice_settings.WAKE_WORD_ENABLED:
            voice_logger.warning("Wake word detection unavailable or disabled in config. PTT/manual mode only.")
            return

        self.wake_word_running = True
        self.wake_word_task = asyncio.create_task(self._wake_word_listen_loop())
        voice_logger.info("Background wake word listening loop started.")

    async def stop_wake_word_loop(self) -> None:
        """
        Stop background wake word loop safely.
        """
        self.wake_word_running = False
        if self.wake_word_task:
            self.wake_word_task.cancel()
            try:
                await self.wake_word_task
            except asyncio.CancelledError:
                pass
            self.wake_word_task = None
        voice_logger.info("Background wake word listening loop stopped.")

    async def _wake_word_listen_loop(self) -> None:
        """
        Background listen loop evaluating microphone chunks against openWakeWord engine.
        """
        import sounddevice as sd
        import collections
        import threading
        import numpy as np

        wake_buffer = collections.deque(maxlen=16000 * 3) # Capped at ~3 seconds of audio
        buffer_lock = threading.Lock()

        def audio_callback(indata, frames, time_info, status):
            if status:
                voice_logger.warning(f"Audio status warning in wake loop callback: {status}")
            with buffer_lock:
                wake_buffer.extend(indata.flatten())

        try:
            stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                callback=audio_callback
            )
            stream.start()
        except Exception as e:
            voice_logger.error(f"Failed to initialize microphone input stream for wake word loop: {e}")
            self.wake_word_running = False
            return

        try:
            chunk_size = 1280
            while self.wake_word_running:
                await asyncio.sleep(0.08) # check every 80ms

                chunk = None
                with buffer_lock:
                    if len(wake_buffer) >= chunk_size:
                        chunk = np.array([wake_buffer.popleft() for _ in range(chunk_size)], dtype=np.float32)

                if chunk is not None:
                    loop = asyncio.get_running_loop()
                    prob = await loop.run_in_executor(None, self.wake_detector.predict, chunk)

                    if prob >= self.wake_detector.threshold:
                        voice_logger.info(f"Wake word matched with confidence {prob:.4f}.")
                        stream.stop()
                        stream.close()

                        asyncio.create_task(self._execute_wake_word_turn())
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            voice_logger.error(f"Error in continuous background wake loop: {e}")
        finally:
            if 'stream' in locals() and stream.active:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass

    async def _execute_wake_word_turn(self) -> None:
        """
        Trigger listening chime, capture voice command up to 15s timeout,
        transcribe, think, synthesize response, and resume wake loop.
        """
        import numpy as np

        # 1. Play listening chime sound
        self._play_notification_chime()

        # 2. Start recording command
        try:
            self.session.start_recording()
            self.recorder.start_recording()
        except Exception as e:
            voice_logger.error(f"Failed to start microphone recording on wake trigger: {e}")
            self.session.set_idle()
            from voice.config import voice_settings
            if voice_settings.WAKE_WORD_ENABLED and self.is_running:
                await self.start_wake_word_loop()
            return

        # 3. Monitor turn recording under max 15-second timeout and silence detection
        start_time = time.time()
        max_duration = 15.0
        silence_threshold = 0.01
        silence_duration = 2.0
        last_speech_time = time.time()

        try:
            while self.session.conversation_state == "listening" and self.is_running:
                await asyncio.sleep(0.1)
                elapsed = time.time() - start_time
                if elapsed >= max_duration:
                    voice_logger.info("Maximum turn recording timeout (15s) reached.")
                    break

                buffer_len = len(self.recorder._buffer)
                if buffer_len > 0:
                    latest_chunk = self.recorder._buffer[-1]
                    rms = np.sqrt(np.mean(latest_chunk**2))
                    if rms > silence_threshold:
                        last_speech_time = time.time()
                    elif time.time() - last_speech_time >= silence_duration:
                        voice_logger.info("Silence detected. Concluding recording turn.")
                        break
        except Exception as e:
            voice_logger.warning(f"Error monitoring turn recording buffer: {e}")

        # 4. Process the turn
        ai_response = await self.trigger_recording_stop()
        voice_logger.info(f"JARVIS turn result: {ai_response}")

        # 5. Resume wake word loop if enabled and service still running
        from voice.config import voice_settings
        if voice_settings.WAKE_WORD_ENABLED and self.is_running:
            await self.start_wake_word_loop()

    def _play_notification_chime(self) -> None:
        """
        Synthesizes and plays a clean, futuristic sinusoidal chime tone in memory.
        No disk files, no external network, 100% local and crash-safe.
        """
        import numpy as np
        import sounddevice as sd
        try:
            sample_rate = 16000
            t1 = np.linspace(0, 0.1, int(sample_rate * 0.1), False)
            tone1 = np.sin(2 * np.pi * 880 * t1) * 0.15
            t2 = np.linspace(0, 0.15, int(sample_rate * 0.15), False)
            tone2 = np.sin(2 * np.pi * 1760 * t2) * 0.15

            chime = np.concatenate([tone1, tone2])
            fade_len = int(sample_rate * 0.05)
            chime[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

            sd.play(chime, sample_rate)
            sd.wait()
        except Exception as e:
            voice_logger.warning(f"Failed to play notification chime: {e}")

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
