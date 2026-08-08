# Phase 8: Browser Automation

This document details the design, safety features, capabilities, and verification loops implemented for Phase 8: Browser Automation.

---

## Capabilities & Browser Tools

JARVIS interacts with the browser securely using Playwright's asynchronous API. All operations are defined as validated browser tools inside the authoritative registry in `tools/registry.py`:

1.  **`open_browser`**: Opens a new browser session or tab.
2.  **`navigate_url`**: Navigates the browser to the specified URL.
3.  **`click_element`**: Clicks page elements (buttons, links) matching selector or description.
4.  **`type_element`**: Fills out input fields.
5.  **`scroll_browser`**: Scrolls page up or down.
6.  **`read_page_content`**: Extracts clean page innerText as markdown blocks.
7.  **`switch_tab`**: Switches page focus to another tab by its index or title.
8.  **`close_tab`**: Closes active browser tab.
9.  **`download_file`**: Captures file download and stores it under configured workspace downloads folder.
10. **`upload_file`**: Uploads workspace file to input element.

---

## Safety & Security Model

The security model is strictly enforced inside `BrowserAutomationService` itself to ensure safety validation is independent of LLM parsing or agent planner layers.

### 1. Safety Tiers
*   **`SAFE`**: Navigation, page reading, tab switching, and scrolling.
*   **`CAUTION`**: Standard clicks, input filling, tab close.
*   **`CONFIRMATION_REQUIRED`**: File uploads, file downloads, or button clicks targeting submit/settings alteration keywords.
*   **`BLOCKED`**: Cookie/token extractions, CAPTCHA bypasses, disabling SSL verification.

### 2. URL Whitelisting & Isolation
*   Only `http://` and `https://` schemes are allowed. Schemes like `file://`, `javascript:`, or `data:` are rejected.
*   `localhost` and `127.0.0.1` are blocked in production environments to prevent local port scanning, but are allowed in test environments.

### 3. File Security
*   Downloads and uploads are confined to the configured workspace directory.
*   Path traversal characters (`..`) and absolute paths outside the target directory are blocked.
*   Dangerous executable file extensions (`.exe`, `.bat`, `.ps1`, `.sh`, `.msi`, `.cmd`) are blocked.

---

## Verification & Testing
Tests utilize a mock `BrowserAutomationService` subclass (`MockBrowserService`) to prevent actual browser instances from opening during offline verification runs.

To verify execution, run the discovery command:
```bash
venv\Scripts\python -m unittest discover -s tests/cognitive
```
Total Phase 8 tests verify URL safety validation, path traversal boundaries, direct execution, confirmation loops, and chat service integration.
