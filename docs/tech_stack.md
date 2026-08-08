# JARVIS Technology Stack

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

## 1. Current Production Stack

These technologies are fully integrated and actively deployed in the current frozen Phase 5.2 release.

### Backend Core
* **Language**: Python 3.11 / 3.12 (asynchronous asyncio loop, type-hinted).
* **API Framework**: FastAPI (>=0.110.0) - High-performance async REST controller routers.
* **Server Wrapper**: Uvicorn[standard] (>=0.28.0) - ASGI server wrapper.
* **Settings & Config**: Pydantic Settings (>=2.2.0) - Validation schemas parsing env parameters.

### Relational Database & ORM
* **Database Engine**: SQLite (for local embedded runtime) & PostgreSQL (for production/cloud scale deployment setups).
* **ORM Layer**: SQLAlchemy 2.0 (asyncio mappings, transactional boundaries, pooled sessions).
* **Migration Manager**: Alembic (tracks schema changes across phases).

> [!NOTE]
> **Architectural Decision Record: SQLite for Local Persistence**
> * **Context**: JARVIS requires persistent memory indexing across reboot cycles that functions offline with zero infrastructure setup.
> * **Decision**: Adopt SQLite. As an embedded process-bound file database, it adds zero runtime dependencies or daemon setup overhead, keeping local installations trivial. By accessing SQLite through SQLAlchemy 2.0 Async ORM repository boundaries, we guarantee 100% PostgreSQL schema compatibility if the user scales to a cloud deployment.

### Vector Search & Embeddings
* **Vector DB**: ChromaDB (PersistentClient local client wrapper storing semantic context and event vectors).
* **Local Embeddings**: SentenceTransformers (Hugging Face `all-MiniLM-L6-v2` loaded locally on CPU).

> [!NOTE]
> **Architectural Decision Record: Local ChromaDB & SentenceTransformers**
> * **Context**: JARVIS requires semantic vector search to resolve similar past dialogue matches and index timeline schedules based on intent.
> * **Decision**: Use a local ChromaDB PersistentClient index driven by the Hugging Face `all-MiniLM-L6-v2` model running offline. Loading model weights locally ensures privacy, isolates the vector pipeline from external internet latency, and enforces zero-cost query operations.

### Artificial Intelligence & LLM Provider
* **Active LLM Provider**: Groq SDK (>=1.6.0) - Fast inference calling `llama-3.3-70b-versatile` or custom formats.
* **Alternative LLM Provider**: OpenAI SDK (>=1.12.0) - BaseLLM abstraction ready.

### Local Voice Pipeline (Offline)
* **Speech-to-Text (STT)**: Faster-Whisper (>=1.2.1) - CTranslate2-backed Whisper engine.
* **Text-to-Speech (TTS)**: Piper TTS (v1.2.0 standalone) - Fast local synthesis binary.
* **Audio Layer**: Sounddevice (>=0.5.5), Soundfile (>=0.14.0), NumPy (>=2.4.6).

---

## 2. Experimental Stack

* *None*. All libraries in active directories have been verified and integrated into the core production stack.

---

## 3. Future Planned Stack

These libraries are slated for integration in upcoming phases.

### Automation & Scripting (Phases 6-7)
* **Browser Automation**: Playwright Python - Headless browser interactions.
* **Desktop Automation**: PyAutoGUI / Keyboard - Native system control wrappers.

### Wake Word Detector (Phase 9)
* **Engine**: openWakeWord - Light model processing continuous audio buffers.

### Graphical User Interface (Phase 10)
* **App Shell**: Tauri / Electron - Desktop HUD frame container.
* **Frontend Web**: React / TailwindCSS (vibrant palettes, responsive layout interface elements).


