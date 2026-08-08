# Phase 7: Browser Automation

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 5.2 (Knowledge Graph, User Profiles & Relational Memory)
* **Next Phase**: Phase 5.3 (User Preferences, Habits & Tasks) [PLANNED]
* **Status**: Planned
* **Version**: v0.7

---

## Objectives
Introduce headless and headed browser automation capabilities to allow JARVIS to browse the web, search Google, read articles, download files, and complete web tasks.

## Features
* Playwright integration for async browser navigation.
* Dynamic DOM parsing, converting web elements to clean markdown for LLM ingestion.
* Input interactions (clicking links, filling inputs, solving basic captcha states).
* Screen capture utility showing visual page states.
* User profile persistence (session cookies) to stay logged in.

## Architecture
```text
ChatRequest
     │
     v
ChatService -> resolves BrowserAutomationTool
                 │
                 v
            Playwright Async Client
                 │
                 v
            Load URLs / fill forms / take screenshots
```

## Files to be Created / Modified
* **`tools/browser_tool.py` [NEW]**: Playwright integration controller.
* **`tools/registry.py` [MODIFY]**: Register browser automation schemas.

## Verification
* Prompt: "Search Google for the latest weather in Tokyo and tell me the temperature."
* Verify Playwright opens, reads weather card element, and summarizes it correctly.

## Known Issues
* Dynamic websites with complex cloudflare protections can block automated requests.

## Future Improvements
* Local vision models to extract data from raw browser screenshots.
