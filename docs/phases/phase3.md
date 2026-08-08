# Phase 3: Voice Interface

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Completed
* **Version**: v0.3

---

## Objectives
Enable local, offline voice interactions for JARVIS using the microphone and speaker, while preserving API stability and modular abstractions.

## Problem Solved
Enabling hands-free offline speech input and synthesis on standard CPUs without blocking the FastAPI async event loop by using thread pool executors.

## Change Log
* **Added**:
  * `app/services/interfaces/base_chat_service.py`: Service layer abstraction.
  * `app/services/chat_service.py`: Unified orchestration logic.
  * `app/services/factory.py`: Central factory to retrieve core backend services.
  * `voice/base_stt.py` & `voice/base_tts.py`: STT and TTS abstract classes.
  * `voice/providers/stt_provider.py` & `voice/providers/piper_provider.py`: Concrete providers.
  * `voice/providers/stt_factory.py` & `voice/providers/tts_factory.py`: Provider factories.
  * `voice/config.py`, `voice/logger.py`, `voice/session.py`: Settings, loggers, and sessions.
  * `voice/microphone.py`: PortAudio audio capture wrapper.
  * `voice/voice_service.py` & `voice/voice_controller.py`: Voice orchestrator and PTT loop.
  * `voice/download_models.py`: Offline downloader tool.
  * `voice/test_voice.py`: Standalone validation runner.
* **Modified**:
  * `app/api/v1/chat.py`: Made route handlers thin controllers injecting ChatService.

## Architecture
```text
KeyPress [Enter]
     │
     v
VoiceController (Keystroke UI shell) -> starts VoiceSession
     │
     v
VoiceService (DI Pipeline Orchestrator)
     ├── 1. AudioRecorder (sounddevice mic stream to numpy array)
     ├── 2. FasterWhisperSTT (BaseSTT provider transcribes text)
     ├── 3. ChatService (BaseChatService processes session response)
     └── 4. PiperTTS (BaseTTS provider runs executable -> sounddevice speaker)
```

## Verification
* Run the downloader tool:
  ```bash
  python -m voice.download_models
  ```
* Execute components verification script:
  ```bash
  python -m voice.test_voice
  ```

* Launch voice console:
  ```bash
  python -m voice.voice_controller
  ```

## Known Limitations
* On Windows, requires `sounddevice` to bind default recording devices correctly. Empty recordings generate warning prompts.

## Future Improvements
* Continuous wake-word listening service.

## Lessons Carried Into Next Phase
* Storing conversational states purely in-memory loses all context on restarts. We need a persistent DB and semantic indexes.

