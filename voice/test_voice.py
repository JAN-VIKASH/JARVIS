"""
Verification script for the voice pipeline components.
"""
import asyncio
import numpy as np
import time
from voice.providers.stt_factory import STTProviderFactory
from voice.providers.tts_factory import TTSProviderFactory
from app.services.factory import ServiceFactory
from voice.session import VoiceSession
from voice.voice_service import VoiceService
from voice.microphone import AudioRecorder
from voice.logger import voice_logger

async def test_microphone():
    print("\n--- Testing Microphone ---")
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    try:
        recorder.start_recording()
        print("Recording for 3 seconds... Please speak into the microphone.")
        await asyncio.sleep(3.0)
        audio = recorder.stop_recording()
        print(f"Recording stopped. Samples captured: {len(audio)}, Shape: {audio.shape}")
        
        max_amplitude = np.max(np.abs(audio))
        print(f"Max Audio Amplitude: {max_amplitude:.4f}")
        if max_amplitude < 0.001:
            print("Warning: Captured audio signal is extremely quiet. Check your microphone volume.")
        else:
            print("Microphone test PASSED.")
        return audio
    except Exception as e:
        print(f"Microphone test FAILED: {e}")
        return None
    finally:
        recorder.close()

async def test_stt(audio_data):
    print("\n--- Testing Speech-to-Text ---")
    if audio_data is None or len(audio_data) == 0:
        print("Skipping STT test: No valid audio data provided.")
        return
        
    try:
        stt = STTProviderFactory.get_provider()
        print("Transcribing captured audio sample...")
        start = time.perf_counter()
        text = await stt.transcribe(audio_data, 16000)
        safe_text = text.encode('ascii', errors='backslashreplace').decode('ascii')
        print(f"Transcription: '{safe_text}'")
        print(f"STT Latency: {time.perf_counter() - start:.4f}s")
        print("Speech-to-Text test PASSED.")
    except Exception as e:
        print(f"Speech-to-Text test FAILED: {e}")

async def test_tts():
    print("\n--- Testing Text-to-Speech ---")
    try:
        tts = TTSProviderFactory.get_provider()
        phrase = "Testing voice synthesis and playback. Offline text to speech is operational."
        print(f"Synthesizing and playing: '{phrase}'")
        start = time.perf_counter()
        await tts.synthesize_and_play(phrase)
        print(f"TTS Playback complete. Latency: {time.perf_counter() - start:.4f}s")
        print("Text-to-Speech test PASSED.")
    except Exception as e:
        print(f"Text-to-Speech test FAILED: {e}")

async def test_end_to_end():
    print("\n--- Testing End-to-End Voice Pipeline ---")
    try:
        stt = STTProviderFactory.get_provider()
        tts = TTSProviderFactory.get_provider()
        chat_service = ServiceFactory.get_chat_service()
        
        session = VoiceSession(session_id="test_voice_session")
        voice_service = VoiceService(stt=stt, tts=tts, chat_service=chat_service, session=session)
        
        await voice_service.start()
        
        print("\nSpeak a query for JARVIS. Starting recording in 1 second...")
        await asyncio.sleep(1.0)
        
        await voice_service.trigger_recording_start()
        print("[Recording started] Speak now. Recording for 4 seconds...")
        await asyncio.sleep(4.0)
        
        print("[Recording stopped] Processing end-to-end pipeline...")
        ai_response = await voice_service.trigger_recording_stop()
        
        safe_response = ai_response.encode('ascii', errors='backslashreplace').decode('ascii')
        print(f"\nFinal response: '{safe_response}'")
        await voice_service.stop()
        print("End-to-End test PASSED.")
    except Exception as e:
        print(f"End-to-End pipeline test FAILED: {e}")

async def main():
    print("="*60)
    print("      JARVIS VOICE PIPELINE VERIFICATION")
    print("="*60)
    
    # 1. Test TTS
    await test_tts()
    
    # 2. Test Microphone
    audio = await test_microphone()
    
    # 3. Test STT
    await test_stt(audio)
    
    # 4. Test E2E Pipeline
    await test_end_to_end()
    
    print("\nVerification completed.")

if __name__ == "__main__":
    asyncio.run(main())
