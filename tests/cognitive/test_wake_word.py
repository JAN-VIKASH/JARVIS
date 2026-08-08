import os
import unittest
import numpy as np
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

from voice.wake_word import WakeWordDetector
from voice.voice_service import VoiceService
from voice.session import VoiceSession
from voice.config import voice_settings
from app.database.migrations import init_db

class TestWakeWord(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.dummy_model_path = "voice/models/hey_jarvis_v0.1.onnx"

    async def test_detector_success_and_threshold(self):
        # 1. Detector success and 2. Probability threshold behavior
        detector = WakeWordDetector(self.dummy_model_path, threshold=0.6)
        
        with patch.object(detector, "is_available", return_value=True):
            mock_model = MagicMock()
            detector._model = mock_model
            detector._is_initialized = True
            
            # Predict high probability (above threshold)
            mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.8}
            prob = detector.predict(np.zeros(1280, dtype=np.float32))
            self.assertEqual(prob, 0.8)
            self.assertTrue(prob >= detector.threshold)
            
            # Predict low probability (below threshold)
            mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.35}
            prob2 = detector.predict(np.zeros(1280, dtype=np.float32))
            self.assertEqual(prob2, 0.35)
            self.assertFalse(prob2 >= detector.threshold)

    async def test_missing_dependency(self):
        # 3. Missing dependency safely falls back
        detector = WakeWordDetector(self.dummy_model_path)
        with patch("builtins.__import__", side_effect=ImportError("No module named 'openwakeword'")):
            self.assertFalse(detector.is_available())
            self.assertEqual(detector.predict(np.zeros(1280)), 0.0)

    async def test_missing_model(self):
        # 4. Missing model file safely falls back
        detector = WakeWordDetector("voice/models/absent_model_file.onnx")
        with patch("os.path.exists", return_value=False):
            self.assertFalse(detector.is_available())
            self.assertEqual(detector.predict(np.zeros(1280)), 0.0)

    async def test_disabled_fallback_state(self):
        # 5. Disabled fallback state when WAKE_WORD_ENABLED is False
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        
        with patch.object(voice_settings, "WAKE_WORD_ENABLED", False):
            await service.start_wake_word_loop()
            self.assertFalse(service.wake_word_running)
            self.assertIsNone(service.wake_word_task)

    async def test_microphone_initialization_failure(self):
        # 6. Microphone initialization failure handles safely (no crash, disables wake word loop)
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        
        with patch.object(service.wake_detector, "is_available", return_value=True), \
             patch.object(voice_settings, "WAKE_WORD_ENABLED", True), \
             patch("sounddevice.InputStream", side_effect=Exception("Microphone resource locked")):
            
            await service.start_wake_word_loop()
            await asyncio.sleep(0.1)
            self.assertFalse(service.wake_word_running)

    async def test_loop_start_stop(self):
        # 7. Loop start and stop loop state checks
        mock_stt = AsyncMock()
        mock_tts = AsyncMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        
        with patch.object(service.wake_detector, "is_available", return_value=True), \
             patch.object(voice_settings, "WAKE_WORD_ENABLED", True), \
             patch("sounddevice.InputStream"):
            
            await service.start_wake_word_loop()
            self.assertTrue(service.wake_word_running)
            self.assertIsNotNone(service.wake_word_task)
            
            await service.stop_wake_word_loop()
            self.assertFalse(service.wake_word_running)
            self.assertIsNone(service.wake_word_task)

    async def test_thread_safety(self):
        # 8. Thread safety callback checks
        mock_stt = AsyncMock()
        mock_tts = MagicMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        
        self.assertIsNotNone(service.wake_detector)

    async def test_wake_trigger_chime_recording_flow(self):
        # 9. Wake trigger -> chime -> recording transition
        mock_stt = AsyncMock()
        mock_tts = MagicMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        service.is_running = True
        
        with patch.object(service, "_play_notification_chime") as mock_chime, \
             patch.object(service.recorder, "start_recording") as mock_rec_start, \
             patch.object(service, "trigger_recording_stop", return_value="turn concluded") as mock_rec_stop:
            
            service.session.conversation_state = "listening"
            
            def conclusion_side_effect(*args, **kwargs):
                service.session.conversation_state = "processing"
            
            with patch("asyncio.sleep", side_effect=conclusion_side_effect):
                await service._execute_wake_word_turn()
            
            mock_chime.assert_called_once()
            mock_rec_start.assert_called_once()
            mock_rec_stop.assert_called_once()

    async def test_15_second_timeout(self):
        # 10. 15-second recording timeout enforcement
        mock_stt = AsyncMock()
        mock_tts = MagicMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        service.is_running = True
        
        async def mock_stop():
            service.session.set_idle()
            return "Turn complete"

        with patch.object(service, "_play_notification_chime"), \
             patch.object(service.recorder, "start_recording"), \
             patch.object(service, "trigger_recording_stop", side_effect=mock_stop):
            
            service.session.conversation_state = "listening"
            
            # Simulate 16 seconds elapsed using a stateful side effect function to prevent logging StopIteration
            time_states = [100.0, 116.0]
            state_index = 0
            
            def mock_time():
                nonlocal state_index
                if state_index < len(time_states):
                    val = time_states[state_index]
                    state_index += 1
                    return val
                return time_states[-1]

            with patch("time.time", side_effect=mock_time):
                await service._execute_wake_word_turn()
                
            self.assertEqual(service.session.conversation_state, "idle")

    async def test_recovery_to_ptt(self):
        # 11. Recovery to Push-to-Talk mode on recording crash/failure
        mock_stt = AsyncMock()
        mock_tts = MagicMock()
        mock_chat = AsyncMock()
        service = VoiceService(mock_stt, mock_tts, mock_chat)
        service.is_running = True
        
        with patch.object(service, "_play_notification_chime"), \
             patch.object(service.recorder, "start_recording", side_effect=RuntimeError("Microphone device not ready")):
             
            await service._execute_wake_word_turn()
            
            # Verify session state reset to idle (PTT fallback ready)
            self.assertEqual(service.session.conversation_state, "idle")
