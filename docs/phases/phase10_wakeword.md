# Phase 10: Wake Word

This document details the design, safety features, capabilities, and verification loops implemented for Phase 10: Wake Word.

---

## Capabilities & Continuous Loop

JARVIS supports continuous offline wake word detection ("Hey Jarvis") to trigger hands-free voice commands.

1. **Background Mic Audio Slicing**: Captures continuous float32 audio segments from the microphone in a non-blocking asyncio thread loop.
2. **Pluggable Wake Word Engine**: Performs hotword evaluation using a local ONNX-based openWakeWord model.
3. **Chime & Voice Command Turn**: Plays a dynamically synthesized sinusoidal audio notification chime, records the user speech command up to a maximum 15-second timeout (or silence conclusion), processes the conversational turn, and then resumes background wake listening.

---

## Safety & Fallback Architecture

### 1. Robust Fallback
* Generic amplitude/frequency volume thresholding is **never** used to fake hotword recognition.
* If the `openwakeword` library is missing or the model file is not pre-downloaded, the system gracefully disables continuous listening mode and falls back to manual Push-to-Talk (PTT) console commands.

### 2. Privacy Enforcements
* Audio segments checked by the wake word loop reside strictly in volatile RAM ring buffers (limited to ~3 seconds).
* Audio buffers are never saved to disk, logged as raw bytes, or transmitted to any external APIs. All wake word inferences run completely locally.

### 3. Concurrency & Concurrency Locks
* Shared ring buffer reads and writes are protected by standard mutex locks (`threading.Lock`) to prevent overlapping write corruption.
* Model evaluation runs on a separate executor thread (`loop.run_in_executor`) to keep loop latency under the required 80ms threshold.

---

## Verification & Testing
Tests mock microphone audio streams and predict probabilities to check loop transitions without downloading weight files or using physical speakers/microphones.

Run command:
```bash
venv\Scripts\python -m unittest tests/cognitive/test_wake_word.py
```
Regression tests verify that all 76 tests (including existing browser/desktop automation and memory engines) remain fully functional.
