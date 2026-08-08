# JARVIS

JARVIS is a production-grade, local-first, low-latency personal AI assistant inspired by the digital assistant created by Tony Stark. Designed to run completely offline for voice interactions (STT/TTS) and semantic indexing, JARVIS integrates vector search (ChromaDB) and relational databases (SQLite) behind clean Repository abstractions and constructor-based Dependency Injection boundaries.

---

## Current Status

* **Version**: v0.5.2
* **Current Implementation Freeze**: Phase 5.2 (Knowledge Graph, User Profiles & Relational Memory)
* **Current Next Phase**: Phase 5.3 (User Preferences, Habits & Tasks)

### Implementation Roadmap Checklist
- [x] **Phase 1**: Backend Foundation (v0.1)
- [x] **Phase 2**: Groq Integration (v0.2)
- [x] **Phase 3**: Voice Interface (v0.3)
- [x] **Phase 4**: Long-Term Memory (v0.4)
- [x] **Phase 4.1**: Advanced Long-Term Memory (v0.4.1)
- [x] **Phase 5.1**: Temporal Reasoning & Event Engine (v0.5.1)
- [x] **Phase 5.1.1**: Event Lifecycle & Timeline Intelligence (v0.5.1.1)
- [x] **Phase 5.2**: Knowledge Graph, User Profiles & Relational Memory (v0.5.2)
- [ ] **Phase 5.3**: User Preferences, Habits & Tasks (⚡ *NEXT*)
- [ ] **Phases 6–12**: Desktop/Browser Automation, Vision, Wake Word, GUI, Multi-Agent, Cloud Sync (⏳ *PLANNED*)

---

## What JARVIS Can Do Today

JARVIS has a robust cognitive core, fully equipped with the following production-quality modules:

* **FastAPI Backend**: Asynchronous ASGI routing server running on Uvicorn, with request validation and unified error mapping.
* **Groq LLM Integration**: Fast inference with the Groq SDK (`llama-3.3-70b-versatile`) incorporating custom exponential backoff retry loops.
* **Provider Abstraction/Factory**: Programmatic separation using `BaseLLM` and `LLMProviderFactory` to support OpenAI, Groq, or placeholder mocks dynamically.
* **Offline Voice Interface**: Local audio transcription via **Faster-Whisper** (CTranslate2-backed Whisper engine) and local synthesis via **Piper TTS** standalone execution.
* **Push-to-Talk (PTT)**: Keystroke-triggered recording pipeline driven by `sounddevice`.
* **SQLite Persistent Memory**: SQLAlchemy 2.0 Async ORM persistence storing dialogue records, user facts, preferences, goals, notes, tasks, and scheduling events.
* **ChromaDB Semantic Memory**: Local vector persistence driven by the Hugging Face `SentenceTransformers` (`all-MiniLM-L6-v2`) model running offline.
* **Hybrid Memory Extraction**: Combines fast deterministic regex key-value extraction with an LLM fallback extractor.
* **Memory Ranking & Decay**: Weighted retrieval scoring (Similarity: 40%, Importance: 20%, Confidence: 15%, Recency: 15%, Frequency: 10%) combined with background importance-based aging/archiving.
* **Temporal event engine**: Calendar event extraction, timezone/date normalizers (e.g. resolving "tomorrow at 5pm"), lifecycle state tracking (`planned`, `completed`, `postponed`, `cancelled`), and semantic vector schedule queries.
* **Knowledge Graph**: Persistent network schemas representing entities, relationships (edges), aliases, and audit logs.
* **Fuzzy Alias Resolution**: Automatic mapping of nicknames or spelling variations using exact matches and Levenshtein edit distance (threshold >= 0.85).
* **Pronoun Resolution**: Tracks recent dialogue context to resolve ambiguous pronouns (e.g. "it", "they", "this project") to canonical entities.
* **Multi-hop Graph Reasoning**: Executes BFS pathfinding algorithms up to depth 3 to build logical inferences over related facts.
* **ContextBuilder & Token Budgeting**: Aggregates contexts in priority order (User Profile > Direct Memories > Semantic Memories > Graph facts > Timeline events) under a strict token threshold (4000 tokens) to prevent context overflows.
* **BackgroundJobManager**: A multithreaded background queue that offloads expensive secondary LLM extraction tasks (parsing entities, edges, profiles) without blocking the conversational response flow.

---

## Architecture

JARVIS is built upon a strict, unidirectional layered architecture. Data and method calls flow downward:

```text
Presentation Layer: PTT CLI Console / Web Interface
       ↓
API Layer: FastAPI Router Endpoints (chat, health)
       ↓
Service Layer: Facade Orchestrators (ChatService, VoiceService)
       ↓
Cognitive Layer: UserProfileEngine, KnowledgeGraphService, Resolvers
       ↓
Repository Layer: Entity, Relationship, Alias, Profile, Event Repositories
       ↓
Storage Layer: SQLite (SQLAlchemy 2.0 Async), ChromaDB Vector Store
       ↓
Infrastructure Layer: BackgroundJobManager, ContextBuilder, Exceptions
```

### Layer Responsibilities
1. **Presentation Layer**: Captures audio input buffers, coordinates PTT console sessions, and plays synthesized audio files.
2. **API Layer**: Declares API routers (`app/api/v1/`), asserts Pydantic validation schemas, and captures request timing telemetry.
3. **Service Layer**: Orchestrates chat workflows, determines message intent, budget contexts, and enqueues background persistence jobs.
4. **Cognitive Layer**: Computes fuzzy alias matches, resolves pronoun references, manages profile preference structures, and executes graph reasoners.
5. **Repository Layer**: Encapsulates direct database queries (SQLite/Chroma), keeping SQL compilers and schema details isolated from business logic.
6. **Storage Layer**: Relational persistent databases (`jarvis.db`) and semantic vector store indexes.
7. **Infrastructure Layer**: Enforces cross-cutting platform concerns (background thread pool queues, custom exception types, and middlewares).

---

## Chat Execution Flow

A single query progresses through the system pipeline step-by-step:

```text
User Request
  → [API Router] receives payload (ChatRequest)
  → [ChatService.execute_chat()] orchestrates workflow
  → [IntentClassifier.classify()] classifies query type
  → [ResponseCache] checks for cached replies (if simple query/recall)
  → [MemoryService] retrieves semantic & long-term conversation logs
  → [UserProfileEngine] fetches structured user profile contexts
  → [PronounResolver] maps pronouns to recent historical entity seeds
  → [KnowledgeGraphService] runs graph expanders over resolved seeds
  → [TimelineEngine] generates timeline feeds (if schedule query)
  → [ContextBuilder] budgets and formats context blocks (up to 4000 tokens)
  → [BaseLLM Provider] (Groq / OpenAI) generates completion
  → [ResponsePostProcessor] and [ResponseValidator] sanitize/constrain answer
  → Save dialogue exchanges to short-term sliding history
  → Spawns background asyncio tasks (save to SQLite and index vector in ChromaDB)
  → Enqueues LLM graph/profile extractions onto [BackgroundJobManager] queue threads
  → Returns response (ChatResponse)
```

---

## Memory Architecture

JARVIS operates a hybrid hierarchical memory model, storing different layers of context in separate data structures:

* **Short-Term / Session Memory**: Tracks the last 10 dialogue turns (20 total messages) in thread-safe memory deques (`app/core/dependencies.py`).
* **Relational Long-Term Memory**: SQL database tables (`user_facts`, `preferences`, `goals`, `notes`, `tasks`) in SQLite, managed by async ORM transactions.
* **Semantic / Vector Memory**: Persistent ChromaDB vector indexes storing embeddings (`all-MiniLM-L6-v2`) of raw dialogue logs and extracted facts to resolve similarity queries.
* **Temporal / Event Memory**: Structured calendar records (`event_memories`) tracked by `TimelineEngine` in SQLite and indexed inside ChromaDB for semantic calendar retrieval.
* **Knowledge Graph Memory**: Structured schemas (`entities`, `relationships`, `entity_aliases`, `entity_merge_audits`) representing networked contexts.
* **User Profile Memory**: Structured key-value preference maps (`user_profiles`) in SQLite representing evolving user states.

---

## Knowledge Graph

The relational Knowledge Graph abstracts complex real-world connections:

* **SQL Models**: `EntityModel` (canonical name, type, mention count, version), `RelationshipModel` (source, target, relationship type, weight, confidence), `AliasModel` (entity references, normalized aliases), and `EntityMergeAuditModel` (records of node merges).
* **Fuzzy Resolvers**: `AliasResolutionEngine` utilizes exact database matches followed by a fuzzy Levenshtein edit distance lookup (threshold >= 0.85) over active entities.
* **Pronoun Resolver**: Resolves relative pronouns to last 5 message referents using word boundary lookups.
* **Graph Traversal**: `KnowledgeGraphService.expand_context()` recursively traces neighboring facts up to depth 3, compiling them into descriptive prompt facts.
* **Export/Import Utility**: `GraphExporter` serializes graph configurations to JSON, DOT, and GraphML file specifications. `GraphImporter` restores graph configurations from JSON outputs.

---

## Voice Architecture

The local Voice Interface operates completely offline:

```text
VoiceController (Console PTT)
       ↓ (captures microphone audio via sounddevice)
VoiceService (Pipeline Orchestrator)
       ↓
FasterWhisperSTT (Transcribes audio on CPU)
       ↓
ChatService (Generates response text via Groq/OpenAI)
       ↓
PiperTTS (Synthesizes audio via standalone binary)
       ↓ (plays back wave files on system speaker)
User Playback
```

---

## API

All HTTP endpoints are versioned under the prefix `/api/v1`. The routers also expose direct root-level aliases.

### 1. System Health Check
* **Path**: `/health`, `/api/v1/health`
* **Method**: `GET`
* **Request**: None
* **Response Schema**:
  ```json
  {
    "status": "ok",
    "assistant": "Jarvis"
  }
  ```
* **Purpose**: Verifies that the API server is active and initialized.

### 2. Chat Interaction
* **Path**: `/chat`, `/api/v1/chat`
* **Method**: `POST`
* **Request Schema (`ChatRequest`)**:
  ```json
  {
    "message": "string (Required, min_length=1)",
    "session_id": "string (Optional, defaults to 'default')",
    "is_voice": "boolean (Optional, defaults to false)"
  }
  ```
* **Response Schema (`ChatResponse`)**:
  ```json
  {
    "response": "string"
  }
  ```
* **Purpose**: Submits user query to the intent, context retrieval, LLM generation, and background extraction pipeline.

---

## Project Structure

```text
JARVIS/
├── app/                        # Main API and Backend Core
│   ├── api/                    # API Route Handlers
│   │   └── v1/                 # Version 1 Endpoints (chat, health)
│   │
│   ├── cognitive/              # Advanced Cognitive Reasoning Modules
│   │   ├── infrastructure/     # Exceptions, Background jobs, Context compilers
│   │   │   ├── background_job_manager.py
│   │   │   ├── context_builder.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── knowledge_graph/    # Graph Extractor, Service, Exporter/Importer, Stats
│   │   │   ├── graph_exporter.py
│   │   │   ├── graph_extractor.py
│   │   │   ├── graph_importer.py
│   │   │   ├── graph_reasoner.py
│   │   │   ├── graph_statistics.py
│   │   │   └── knowledge_graph_service.py
│   │   │
│   │   ├── profile/            # User profile preferences extractor & engine
│   │   │   └── user_profile_engine.py
│   │   │
│   │   └── resolution/         # Alias resolution and Pronoun resolvers
│   │       ├── alias_resolution_engine.py
│   │       └── pronoun_resolver.py
│   │
│   ├── config/                 # Configurations Setup
│   │   ├── settings.py         # Settings Loader (BaseSettings + toggles)
│   │   └── logging.py          # Unified log setup handler
│   │
│   ├── core/                   # Core App Infrastructure
│   │   ├── constants.py
│   │   ├── dependencies.py     # Injection providers
│   │   ├── exceptions.py       # Custom exception handlers
│   │   └── middleware.py       # Timing and correlation ID mapping
│   │
│   ├── database/               # Database Relational Model & Repositories
│   │   ├── repositories/       # Repositories (entity, relationship, alias, profile, event)
│   │   │   ├── alias_repository.py
│   │   │   ├── entity_repository.py
│   │   │   ├── event_repository.py
│   │   │   ├── relationship_repository.py
│   │   │   └── user_profile_repository.py
│   │   │
│   │   ├── base.py
│   │   ├── migrations.py       # Schema migrator
│   │   ├── models.py           # SQLAlchemy tables declaration
│   │   └── session.py          # Async connection session generator
│   │
│   ├── models/                 # Validation Schemas
│   │   └── chat_models.py      # Request/Response data models
│   │
│   ├── prompts/
│   │   └── system_prompt.txt
│   │
│   ├── services/               # Core Services layer
│   │   ├── cognitive/          # Temporal reasoning services (event extractor, time normalizer, timeline)
│   │   │   ├── duplicate_event_resolver.py
│   │   │   ├── event_extractor.py
│   │   │   ├── event_update_detector.py
│   │   │   ├── time_normalizer.py
│   │   │   └── timeline_engine.py
│   │   │
│   │   ├── interfaces/         # Core abstractions
│   │   │   └── base_chat_service.py # Chat service interface
│   │   │
│   │   ├── llm/                # LLM Integration Layer (Groq, OpenAI providers)
│   │   │   ├── base.py
│   │   │   ├── factory.py
│   │   │   ├── generation_config.py
│   │   │   ├── groq_provider.py
│   │   │   ├── openai_provider.py
│   │   │   └── placeholder.py
│   │   │
│   │   ├── response/           # Chat prompt building, validation, and cache layer
│   │   │   ├── intent_classifier.py
│   │   │   ├── post_processor.py
│   │   │   ├── prompt_builder.py
│   │   │   ├── response_cache.py
│   │   │   └── response_validator.py
│   │   │
│   │   ├── chat_service.py     # ChatService orchestrator
│   │   └── factory.py          # ServiceFactory registry
│   │
│   ├── utils/
│   │   ├── file_loader.py
│   │   ├── helpers.py
│   │   └── logger.py
│   │
│   └── main.py                 # FastAPI system initializer
│
├── docs/                       # Project Documentation System
│   ├── diagrams/               # Architecture Flowcharts (Mermaid)
│   ├── phases/                 # Historical Phase records
│   └── JARVIS_MASTER_CONTEXT.md # Master context handbook
│
├── memory/                     # Conversation Memory layer
│   ├── base.py                 # BaseMemory abstraction
│   ├── base_memory.py
│   ├── chroma_repository.py    # Local ChromaDB embeddings indexes storage
│   ├── conflict_resolver.py
│   ├── decay_service.py
│   ├── embedding.py
│   ├── extractor.py
│   ├── filter.py
│   ├── in_memory.py            # Sliding deque memory manager
│   ├── llm_extractor.py
│   ├── memory_factory.py       # Dependency Injection container
│   ├── memory_service.py       # Main Memory Service orchestrator
│   ├── repository.py
│   ├── scorer.py
│   ├── search.py
│   ├── sqlite_repository.py    # SQLite direct conversation logs storage
│   ├── test_memory.py
│   └── test_personality.py
│
├── tests/                      # Testing Framework Suite
│   └── cognitive/              # Advanced tests
│       ├── test_event_lifecycle.py
│       ├── test_graph_engine.py
│       └── test_temporal_engine.py
│
├── voice/                      # Voice Interface module
│   ├── bin/                    # Standalone audio binaries (Rhasspy Piper) (gitignored)
│   ├── models/                 # Audio ONNX model weights (gitignored)
│   ├── providers/              # STT and TTS Engines
│   │   ├── piper_provider.py
│   │   ├── tts_factory.py
│   │   ├── stt_provider.py
│   │   └── stt_factory.py
│   │
│   ├── config.py
│   ├── download_models.py      # Download models and binaries
│   ├── logger.py
│   ├── microphone.py           # sounddevice audio PTT recorder
│   ├── session.py
│   ├── test_voice.py
│   ├── voice_controller.py     # Console audio PTT helper
│   └── voice_service.py        # Pipeline orchestrator
│
├── .env.example                # Configuration template
├── .gitignore                  # Git settings
├── README.md                   # Setup guide
├── requirements.txt            # Package list
└── run.py                      # Server starter script
```

---

## Technology Stack

### Current (Active)
* **FastAPI (>=0.110.0) & Uvicorn**: High-performance asynchronous REST routers.
* **SQLAlchemy 2.0 (>=2.0.0) & aiosqlite**: Asynchronous ORM mappings and SQLite database connections.
* **ChromaDB (>=0.4.0)**: Offline vector persistent storage client.
* **SentenceTransformers (>=2.2.2)**: Local execution of `all-MiniLM-L6-v2` embeddings.
* **Groq SDK (>=1.6.0) & OpenAI SDK**: Local provider configurations.
* **Faster-Whisper (>=1.2.1)**: Local speech transcription executing on CPU.
* **Piper TTS (v1.2.0)**: stand-alone text-to-speech rendering executable.
* **Sounddevice (>=0.5.5), Soundfile, NumPy**: Audio recording input buffers.

### Planned (Future Phases)
* **Playwright Python**: Browser interaction driver scripts (Phases 6–7).
* **PyAutoGUI / Keyboard**: Local desktop input simulation engines (Phases 6–7).
* **openWakeWord**: continuous listening hotword triggers (Phase 9).
* **Tauri / Electron**: Desktop HUD shell frameworks (Phase 10).
* **React & TailwindCSS**: HUD styling framework interfaces (Phase 10).

---

## Installation

### 1. Environment Setup
JARVIS runs on Python 3.11 or 3.12. Configure your virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source venv/bin/activate
```

### 2. Install Packages
Install dependencies from the workspace root:

```bash
pip install -r requirements.txt
```

### 3. Setup Configuration
Configure environment variables from the template:

```bash
copy .env.example .env
```

Edit your `.env` configuration to include API keys and choose providers:
```env
LLM_PROVIDER="groq"
GROQ_API_KEY="gsk_..."
MODEL_NAME="llama-3.3-70b-versatile"
```

### 4. Fetch Standalone Voice Models & Executables
Download the local Faster-Whisper weights, Piper TTS binaries, and voice configurations:

```bash
python -m voice.download_models
```
*Note: This command populates `voice/bin/` and `voice/models/` directories, which are excluded from version control.*

### 5. Database Setup
SQLite database schemas are **automatically initialized at runtime** inside the application context. No manual database setup scripts or migration commands are required for starting up.

---

## Running JARVIS

### 1. Launch Backend API Server
Start the Uvicorn REST API server:

```bash
python run.py
```
The FastAPI instance will be available at `http://127.0.0.1:8000`.

### 2. Start interactive Voice Client
Ensure the FastAPI server is active, then launch the console PTT controller in a separate terminal:

```bash
python -m voice.voice_controller
```
Press `Enter` to record, speak your query, and press `Enter` again to transmit.

---

## Testing

Verify the cognitive modules by executing the integration test suite:

```bash
# Run Graph Engine tests
venv\Scripts\python -m unittest tests.cognitive.test_graph_engine

# Run Event Lifecycle tests
venv\Scripts\python -m unittest tests.cognitive.test_event_lifecycle
```
*Note: `tests.cognitive.test_temporal_engine` contains known issues with database deletion queries in the test mock data and is excluded from validation suite runs.*

---

## Configuration

Configurations are declared in `app/config/settings.py` and are parsed using `pydantic-settings` from your `.env` file. Important variables include:

* `LLM_PROVIDER`: Injected LLM provider subclass ("groq", "openai", "placeholder").
* `DATABASE_URL`: Connection URL (`sqlite+aiosqlite:///database/jarvis.db`).
* `CHROMA_DB_PATH`: Folder path to local vector databases (`database/chroma`).
* `EMBEDDING_MODEL`: Name of SentenceTransformers embedding models.
* `ENABLE_GRAPH`: Global feature toggle to activate/deactivate Knowledge Graph expansions.
* `ENABLE_USER_PROFILE`: Toggle to activate/deactivate structured profile updates.

*Secrets must be kept out of version control and stored only in your local `.env`.*

---

## Design Principles

* **Repository Pattern**: Keeps data transaction queries fully separated from execution services. Swapping databases only requires editing repositories.
* **Dependency Injection (DI)**: Declarative constructor parameters enable simple class testing and mock injections.
* **Factory Pattern**: Centralizes object lifespan configurations inside `ServiceFactory` and `MemoryFactory` modules.
* **Thin API Controllers**: API endpoint functions validate formats and immediately hand off routing logic to services.
* **Local-first Architecture**: All speech models, embeddings, and database indexes operate offline without network latency or external costs.

---

## Development Roadmap

* [x] **Phase 1: Backend Foundation**: FastAPI structure, logging, sliding history.
* [x] **Phase 2: Groq Integration**: SDK, token telemetry, retry loops.
* [x] **Phase 3: Voice Interface**: Faster-Whisper, Piper TTS, PTT shell.
* [x] **Phase 4: Long-Term Memory**: SQLite persistence, ChromaDB vector indexing.
* [x] **Phase 4.1: Advanced Memory**: Match fallback pipelines, decay services, weighted retrieval.
* [x] **Phase 5.1: Temporal Reasoning**: UTC time normalizers, timeline engines.
* [x] **Phase 5.1.1: Event Lifecycle**: State tracking, event duplicate resolvers, vector events.
* [x] **Phase 5.2: Relational Memory**: Fuzzy alias resolutions, pronoun decoders, Knowledge Graph, User Profile engines.
* [ ] **Phase 5.3: User Preferences, Habits & Tasks** (⚡ *NEXT*)
* [ ] **Phases 6–12**: OS Desktop controls, Playwright web browser scraping, OCR Vision, Wake Word listening daemon, Tauri client GUI HUD panel, Multi-agent scheduling, encrypted Cloud Sync.

---

## Documentation

* [docs/JARVIS_MASTER_CONTEXT.md](docs/JARVIS_MASTER_CONTEXT.md): Primary developer onboarding manual.
* [docs/roadmap.md](docs/roadmap.md): Complete milestone index mappings.
* [docs/architecture.md](docs/architecture.md): Layer definitions and ADR charts.
* [docs/api.md](docs/api.md): Programmatic and REST schema reference lists.
* [docs/folder_structure.md](docs/folder_structure.md): Repository tree configurations.
* [docs/tech_stack.md](docs/tech_stack.md): Current and planned packages specs.
* [docs/coding_guidelines.md](docs/coding_guidelines.md): Structural conventions and ADRs.
* [docs/phases/](docs/phases/): Historical sprint archives.

---

## Future Direction (Planned)

* **Phase 5.3**: Parse structured user routines, routines/habit graphs, and task items.
* **Phase 6**: Integrate mouse and keyboard listeners to run OS command operations.
* **Phase 7**: Configure Playwright automated browsing interfaces.
* **Phase 8**: Local image parsing with OCR ONNX pipelines.
* **Phase 9**: Standalone wake word listening daemon ("Hey Jarvis").
* **Phase 10**: Electron/Tauri graphical HUD console panels.

---

## Important Development Rules

* **Do not bypass repository abstractions**: Relational queries must remain in `app/database/repositories/`. Never import database session makers or SQLAlchemy models in routers/services.
* **Do not put business logic in API routes**: Route handlers must validate payload schemas and execute services.
* **Preserve provider factory contracts**: LLM, STT, and TTS engines must remain decoupled from specific vendors.
* **Preserve base interfaces**: Do not modify parameter signatures of `BaseLLM`, `BaseMemory`, `BaseSTT`, `BaseTTS`, or `BaseChatService`.
* **Keep secrets out of source control**: Store all API keys and credentials in `.env` only.
* **Keep local/offline embedding and voice requirements intact**: Embeddings and STT/TTS models must execute locally. SentenceTransformers must load only from local cache (`local_files_only=True`).
* **Do not introduce localhost HTTP calls**: Avoid introducing HTTP communication for internal service layers.
* **Preserve backwards compatibility**: Ensure new modules do not disrupt established features.
