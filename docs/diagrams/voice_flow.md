# Voice Interface Pipeline Flow Diagram

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant VC as VoiceController
    participant VS as VoiceService
    participant Rec as AudioRecorder (sounddevice)
    participant STT as FasterWhisperSTT (BaseSTT)
    participant CS as ChatService (BaseChatService)
    participant TTS as PiperTTS (BaseTTS)

    User->>VC: Press [Enter]
    VC->>VS: trigger_recording_start()
    VS->>Rec: start_recording()
    Note over Rec: Buffers mic samples asynchronously
    
    User->>VC: Press [Enter] again
    VC->>VS: trigger_recording_stop()
    VS->>Rec: stop_recording()
    Rec-->>VS: returns raw float32 array
    
    VS->>STT: transcribe(audio_data, 16000)
    Note over STT: Runs off event loop via Executor thread
    STT-->>VS: returns transcribed prompt string
    
    VS->>CS: execute_chat(ChatRequest(is_voice=True))
    activate CS
    Note over CS: ChatService applies voice length constraints
    CS-->>VS: returns AI response text
    deactivate CS
    
    VS->>TTS: synthesize_and_play(ai_response)
    activate TTS
    Note over TTS: Runs piper.exe via subprocess off loop
    TTS->>User: Playback WAV audio to speakers
    TTS-->>VS: finished playback
    deactivate TTS
    
    VS-->>VC: response execution completed
```

