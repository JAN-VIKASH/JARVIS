# Phase 9: Vision

This document details the design, safety features, capabilities, and verification loops implemented for Phase 9: Vision.

---

## Capabilities & Vision Tools

JARVIS interacts with the visual screen state securely using PyAutoGUI/Pillow for screen capture, Tesseract OCR for text/coordinate detection, and lazy-loaded quantized ONNX-based Florence-2 VLM for page QA/description.

All operations are defined as validated vision tools inside the authoritative registry in `tools/registry.py`:

1.  **`take_screenshot`**: Captures screen frame of primary display monitor.
2.  **`read_screen`**: Performs local OCR on current screen, returning text and bounding boxes.
3.  **`find_screen_element`**: Locates element center and bounding box coordinates for target text.
4.  **`describe_screen`**: Generates visual description of the screen utilizing VLM.

---

## Safety & Security Model

### 1. Offline & Local Execution
*   All vision processing is strictly offline. Bounding boxes, coordinates, and descriptions are computed locally. Image bytes are never sent to external cloud APIs (e.g. Groq).

### 2. Privacy & Screenshot Cleanup
*   Screenshots are temporarily saved in the local workspace downloads folder and purged immediately in `finally` execution cleanup blocks.
*   If cleanup fails, only path/error metadata is written to application logs; raw screenshot pixels are never logged or stored.

### 3. Coordinate Separation
*   `VisionService` does not perform mouse movement or clicks. It returns bounding boxes and target center coordinates.
*   `DesktopAutomationService` remains the sole component permitted to execute physical input/clicks.

---

## Model Decisions & Resource Footprint

### 1. OCR Engine
*   **Engine**: Tesseract OCR (via `pytesseract` wrapper).
*   **System Binary**: Requires host system `tesseract` binary.
*   **Graceful Fallback**: If the binary is missing, falls back to `MockOCREngine` (yields mock bounding boxes based on test/UI metadata) rather than crashing.

### 2. VLM Engine
*   **Model**: Quantized Florence-2 (INT4 base version).
*   **Expected Path**: `models/vision/florence2_base_int4.onnx` (model size ~230MB).
*   **Optional Load**: VLM loading is completely optional and lazy. If the weight file is missing, VLM-related tools return a controlled `MODEL_UNAVAILABLE` message.

---

## Verification & Testing
Tests mock screen capture, OCR, and ONNX Runtime CPU session runs to verify all lifecycles cleanly in a sandbox environment without heavy dependency/weight downloads.

Run command:
```bash
venv\Scripts\python -m unittest tests/cognitive/test_vision.py
```
Regression validation verifies that all 66 tests (including existing browser/desktop automation) pass.
