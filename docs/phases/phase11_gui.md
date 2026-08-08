# Phase 11: Desktop Graphical User Interface (GUI)

This document details the design, safety architecture, and capabilities implemented in Phase 11: Desktop Graphical User Interface (GUI).

---

## Capabilities & Architecture

Phase 11 introduces a high-end, futuristic, Stark-inspired Single Page Application HUD served directly from the FastAPI server at `/gui`.

1. **Futuristic Holographic Aesthetic**: Styled using Rajdhani and Orbitron typography with cyan-glowing glassmorphic panel cards, dynamic visualizers, and state alerts.
2. **Real-time Event Streaming (SSE)**: Streams voice turn updates and agent planning transitions in real-time from the backend to the UI over a persistent SSE connection (`/api/v1/gui/events`).
3. **Canvas Audio Waveform**: Client-side sine-wave visualization animating on Canvas during active microphone states, removing any web client recording hardware overhead.
4. **Configuration Manager**: Panel to adjust safe allowlisted voice settings (`WAKE_WORD_ENABLED`, threshold, STT/TTS providers, etc.).

---

## Concurrency & Safety Controls

### 1. Non-Blocking Event Bus (`GUIEventBus`)
* Emits events to all connected browser clients using individual, bounded client queues (`maxsize=100`) to prevent memory leaks.
* Event publishing is completely synchronous and non-blocking (`put_nowait()`), guaranteeing that voice pipeline processing and agent execution threads never stall due to slow network clients.
* Disconnected clients are safely cleaned up and removed from the active subscriber set inside `finally` blocks when cancellations are caught.

### 2. Strict Configuration Allowlist & Security boundaries
* **GET `/gui/settings`**: Excludes any secrets, credentials, or `.env` details from responses, masking existing entries and showing only safe, GUI-approved configuration metrics.
* **POST `/gui/settings`**: Rejects any key not explicitly defined in the safe configuration allowlist (`ALLOWLIST`) with an HTTP 400 Bad Request error. Overwriting environment parameters or API keys is completely blocked.
* **Local-Only Execution**: The FastAPI server remains strictly bound to `127.0.0.1`. The frontend does not expose any direct OS, desktop, or browser execution endpoints; all prompts utilize the existing `/chat` validation checks and confirmation gates.
* **Synchronized Env Persistence**: Settings changes are updated in RAM (taking effect immediately) and synchronously modified in the `.env` file using a precise line parser, preserving credentials and other configurations.

---

## Verification & Testing
New unit and integration tests are added under `tests/cognitive/test_gui_endpoints.py`.

Run command:
```bash
venv\Scripts\python -m unittest tests/cognitive/test_gui_endpoints.py
```
Regression tests verify that all 83 tests (including existing memory managers, vision coordinates, and wake word detectors) pass.
