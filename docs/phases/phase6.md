# Phase 6: Desktop Automation

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 6 (Desktop Automation)
* **Next Phase**: Phase 7 (Browser Automation) [PLANNED]
* **Status**: Completed
* **Version**: v0.6

---

## Objectives
Automate OS-level desktop tasks, enabling JARVIS to manage windows, control mouse/keyboard inputs, launch programs, and manage basic system operations.

## Features
* Mouse pointer control (moving, clicking, dragging) and keyboard key injection (typing text, hitting hotkeys) via libraries (like PyAutoGUI).
* Active window management (focusing applications, closing tabs, tiling screens).
* Launching local programs (opening VS Code, starting browser, starting notepad).
* Volume and brightness control, lock screen commands, and audio output device toggles.

## Architecture
```text
ChatService -> resolves DesktopAutomationTool
                 │
                 v
            PyAutoGUI / OS APIs
                 │
                 v
            Simulate input clicks / run processes on host OS
```

## Files Created / Modified
* **`app/services/desktop_automation_service.py` [NEW]**: Orchestrates parsing safety limits and background operations.
* **`tools/desktop_tool.py` [NEW]**: Native PyAutoGUI and PyGetWindow wrapper.
* **`tools/registry.py` [NEW]**: Exposes closed command parameters and LLM system prompts.
* **`tests/cognitive/test_desktop_automation.py` [NEW]**: Unit and integration test suite with mocking.
* **`app/services/response/intent_classifier.py` [MODIFY]**: Classifies desktop action queries.
* **`app/services/chat_service.py` [MODIFY]**: Routes queries and pending confirmations to the service.
* **`app/services/factory.py` [MODIFY]**: Dependency injection factory singleton registration.
* **`requirements.txt` [MODIFY]**: Dependency updates.

## Verification
* Prompt: "Open notepad, write 'Jarvis is alive' and save it."
* Verify application launches and executes keys successfully.

## Known Issues
* Focus changes or popups can derail PyAutoGUI automation workflows.

## Future Improvements
* Screen vision analysis to locate icons dynamically.
