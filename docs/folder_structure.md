# JARVIS Folder Structure

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

## 1. Workspace Directory Tree

The directory layout of the JARVIS repository is configured as follows:

```text
jarvis/
│
├── app/                        # Main API and Backend Core
│   ├── api/                    # API Route Handlers
│   │   └── v1/                 # Version 1 Endpoints (chat, health)
│   │
│   ├── cognitive/              # Advanced Cognitive Reasoning Modules
│   │   ├── infrastructure/     # Exceptions, Background jobs, Context compilers
│   │   ├── knowledge_graph/    # Graph Extractor, Service, Exporter/Importer, Stats
│   │   ├── profile/            # User profile preferences extractor & engine
│   │   └── resolution/         # Alias resolution and Pronoun resolvers
│   │
│   ├── config/                 # Configurations Setup
│   │   ├── settings.py         # Settings Loader (BaseSettings + toggles)
│   │   └── logging.py          # Unified log setup handler
│   │
│   ├── core/                   # Core App Infrastructure
│   │   ├── dependencies.py     # Injection providers
│   │   ├── exceptions.py       # Custom exception handlers
│   │   └── middleware.py       # Timing and correlation ID mapping
│   │
│   ├── database/               # Database Relational Model & Repositories
│   │   ├── repositories/       # Repositories (entity, relationship, alias, profile, event)
│   │   ├── models.py           # SQLAlchemy tables declaration
│   │   ├── session.py          # Async connection session generator
│   │   └── migrations/         # Alembic database migrations scripts
│   │
│   ├── models/                 # Validation Schemas
│   │   └── chat_models.py      # Request/Response data models
│   │
│   ├── services/               # Core Services layer
│   │   ├── cognitive/          # Temporal reasoning services (event extractor, time normalizer, timeline)
│   │   ├── interfaces/         # Core abstractions
│   │   │   └── base_chat_service.py # Chat service interface
│   │   ├── llm/                # LLM Integration Layer (Groq, OpenAI providers)
│   │   ├── response/           # Chat prompt building, validation, and cache layer
│   │   ├── chat_service.py     # ChatService orchestrator
│   │   └── factory.py          # ServiceFactory registry
│   │
│   └── main.py                 # FastAPI system initializer
│
├── docs/                       # Project Documentation System
│   ├── diagrams/               # Architecture Flowcharts (Mermaid)
│   ├── phases/                 # Historical Phase records
│   └── JARVIS_MASTER_CONTEXT.md # Master context handbook
│
├── memory/                     # Conversation Memory layer
│   ├── memory_service.py       # Main Memory Service orchestrator
│   ├── memory_factory.py       # Dependency Injection container
│   ├── base.py                 # BaseMemory abstraction
│   ├── in_memory.py            # Sliding deque memory manager
│   ├── sqlite_repo.py          # SQLite direct conversation logs storage
│   └── chroma_repo.py          # Local ChromaDB embeddings indexes storage
│
├── tests/                      # Testing Framework Suite
│   ├── cognitive/              # Advanced tests (test_event_lifecycle.py, test_graph_engine.py)
│   └── ...                     # Core engine unit tests
│
├── voice/                      # Voice Interface module
│   ├── bin/                    # Standalone audio binaries (Rhasspy Piper)
│   ├── models/                 # Audio ONNX model weights
│   ├── providers/              # STT and TTS Engines (piper_provider, stt_provider)
│   ├── microphone.py           # sounddevice audio PTT recorder
│   ├── voice_service.py        # Pipeline orchestrator
│   └── voice_controller.py     # Console audio PTT helper
│
├── .env                        # Local configuration settings (Secret)
├── .env.example                # Configuration template
├── run.py                      # Uvicorn entry point script
└── requirements.txt            # Package list
```

---

## 2. Folder-by-Folder Specifications

### Directory: `app/api/v1/`
* **Purpose**: Hosts REST endpoint handlers.
* **Responsibilities**: Receives HTTP requests, validates Pydantic schemas, and routes execution to injected services.
* **Key Files**: `chat.py` (chat REST controller), `health.py` (health checks).
* **Dependencies**: `app/models/`, `app/services/factory.py`.
* **Future Extension Point**: To add a new REST API endpoint, create a route handler file in this folder and register it in `app/main.py`.

### Directory: `app/cognitive/`
* **Purpose**: Contains advanced multi-hop relational context reasoning.
* **Responsibilities**: Entity fuzzy aliasing, pronoun reference resolution, profile preference evolutions, and export visualizations.
* **Key Files**:
  * `resolution/alias_resolution_engine.py` (resolves spelling variations/aliases).
  * `knowledge_graph/knowledge_graph_service.py` (coordinates persistent entity graph operations).
  * `profile/user_profile_engine.py` (manages preference lists).
* **Dependencies**: `app/database/repositories/`, `app/cognitive/infrastructure/`, `app/services/llm/`.
* **Future Extension Point**: To add a new cognitive resolver (e.g. sentiment tracking), add a submodule subfolder under this directory.

### Directory: `app/database/`
* **Purpose**: Coordinates physical relational storage connections and mappings.
* **Responsibilities**: Executing transactional mutations and abstracting SQL statements.
* **Key Files**:
  * `models.py` (SQL tables definitions).
  * `session.py` (async transactional session maker).
  * `repositories/entity_repository.py` (handles entity-merge audits).
* **Dependencies**: `app/config/settings.py`.
* **Future Extension Point**: To support another relational database engine (like MySQL), modify parameters inside `session.py` and run migrations via `migrations/` scripts.

### Directory: `app/services/`
* **Purpose**: Orchestrates central domain operations.
* **Responsibilities**: Formatting systems prompts, checking validation limits, caching responses, and parsing temporal timelines.
* **Key Files**:
  * `chat_service.py` (main conversation coordinator).
  * `cognitive/timeline_engine.py` (timeline builder).
  * `response/prompt_builder.py` (prompt assembly).
* **Dependencies**: `app/cognitive/`, `memory/`.
* **Future Extension Point**: To add new conversation intent processors, register them within `app/services/chat_service.py` and `app/services/response/prompt_builder.py`.

### Directory: `memory/`
* **Purpose**: Manages long-term retrieval pipelines and vector indexes.
* **Responsibilities**: Scoring memory queries, decaying inactive records, and storing semantic indexes.
* **Key Files**:
  * `memory_service.py` (hierarchical recall controller).
  * `memory_factory.py` (caching DI container).
  * `sqlite_repo.py` (saves raw logs).
  * `chroma_repo.py` (saves embedding dimensions).
* **Dependencies**: `app/database/repositories/`.
* **Future Extension Point**: To add external vector service providers (like Qdrant), write a new client class implementing `BaseMemoryRepository` in this directory.

### Directory: `voice/`
* **Purpose**: Audio transcription and voice synthesis.
* **Responsibilities**: Captures local device microphone streams and manages sound playback threads.
* **Key Files**:
  * `microphone.py` (sounddevice listener).
  * `voice_service.py` (PTT pipeline builder).
* **Dependencies**: `app/services/factory.py`.
* **Future Extension Point**: To swap synthesis providers, register the new client model in `voice/providers/`.

