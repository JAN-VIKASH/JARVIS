# Phase 9: Wake Word

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 5.2 (Knowledge Graph, User Profiles & Relational Memory)
* **Next Phase**: Phase 5.3 (User Preferences, Habits & Tasks) [PLANNED]
* **Status**: Planned
* **Version**: v0.9

---

## Objectives
Introduce continuous offline wake word listening ("Hey Jarvis") to trigger the assistant hands-free.

## Features
* Integration of a lightweight, local wake word detection engine (like `openWakeWord`).
* Dynamic background mic recording parser that checks audio slices in real-time.
* Low CPU utilization loop that runs continuously.
* Transition from PTT (Push-to-Talk) to continuous listening mode.

## Architecture
```text
Continuous mic stream
     │
     v
Background Audio Buffer
     │
     v
openWakeWord Engine (Lightweight local neural model)
     │
     ├── If matches target ("Hey Jarvis") -> Play wake sound, start VoiceService
     └── Else -> discard buffer
```

## Files to be Created / Modified
* **`voice/wake_word.py` [NEW]**: openWakeWord integration engine.
* **`voice/voice_service.py` [MODIFY]**: Connect continuous listener.

## Verification
* Speak "Hey Jarvis" and verify that recording triggers automatically.

## Known Issues
* High false alarm rates in noisy environment settings.

## Future Improvements
* User voice fingerprinting (recognizing only owner voice).
