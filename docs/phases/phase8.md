# Phase 8: Vision

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Planned
* **Version**: v0.8

---

## Objectives
Equip JARVIS with vision capabilities. Enable processing and understanding screenshots, images, and visual elements locally on CPU.

## Features
* Screen snapshot capture utility.
* Local OCR (Optical Character Recognition) using lightweight ONNX engines.
* Local Vision-Language Model (VLM) execution (like quantized Florence-2 or Moondream) using ONNX Runtime.
* Coordinate finder to calculate where a specific button or text is located visually on screen.

## Architecture
```text
Capture Screenshot
     │
     v
Quantized VLM (ONNX Runtime CPU)
     │
     v
Coordinates & Page Summary
     │
     v
ChatService (Incorporate visual context to coordinate clicks)
```

## Files to be Created / Modified
* **`tools/vision_tool.py` [NEW]**: Screenshot and local ONNX image processor.
* **`tools/registry.py` [MODIFY]**: Register vision tools.

## Verification
* Prompt: "Describe what is on my screen right now."
* Verify screen capture saves, VLM processes it, and generates a valid description.

## Known Issues
* High latency on older CPUs when running VLMs.

## Future Improvements
* Video stream feed processing.
