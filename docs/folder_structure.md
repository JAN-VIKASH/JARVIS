# JARVIS Folder Structure

* **Last Updated**: 2026-08-08
* **Current Phase**: Phase 5.3 (User Preferences, Habits & Tasks)
* **Status**: Freeze
* **Version**: v0.5.3

---

## 1. Workspace Directory Tree

The directory layout of the JARVIS repository is configured as follows:

```text
JARVIS/
│
├── app/                        # Main API and Backend Core
│   ├── api/                    # API Route Handlers
│   │   └── v1/                 # Version 1 Endpoints
│   │       ├── chat.py         # Chat conversation endpoint
│   │       └── health.py       # Health status endpoint
│   │
│   ├── cognitive/              # Advanced Cognitive Reasoning Modules
│   │   ├── infrastructure/     # Core support components
│   │   │   ├── background_job_manager.py # Background task worker thread queue
│   │   │   ├── context_builder.py        # Token-budgeted context compiler
│   │   │   └── exceptions.py             # Cognitive specific exception types
│   │   │
│   │   ├── knowledge_graph/    # Relational entity-graph modules
│   │   │   ├── graph_exporter.py         # Exporter for JSON, DOT, and GraphML
│   │   │   ├── graph_extractor.py        # LLM-driven graph extraction engine
│   │   │   ├── graph_importer.py         # Backup JSON state restorer
│   │   │   ├── graph_reasoner.py         # Multi-hop pathfinding (BFS)
│   │   │   ├── graph_statistics.py       # Node, edge, and density metrics
│   │   │   └── knowledge_graph_service.py # Main graph coordinator facade
│   │   │
│   │   ├── profile/            # Profile preferences management
│   │   │   └── user_profile_engine.py    # Evolving preferences engine
│   │   │
│   │   └── resolution/         # Cognitive context solvers
│   │       ├── alias_resolution_engine.py # Fuzzy Levenshtein alias matcher
│   │       └── pronoun_resolver.py       # Contextual pronoun referent resolver
│   │
│   ├── config/                 # Configurations Setup
│   │   ├── settings.py         # Settings Loader (BaseSettings + toggles)
│   │   └── logging.py          # Unified logging config setup
│   │
│   ├── core/                   # Core App Infrastructure
│   │   ├── constants.py        # Constants and parameters
│   │   ├── dependencies.py     # Injection providers (LLM, Memory, Prompt)
│   │   ├── exceptions.py       # Central exception handler mappings
│   │   └── middleware.py       # Timing and correlation ID middleware
│   │
│   ├── database/               # Relational Database Mappings & Setup
│   │   ├── repositories/       # Isolated domain queries (SQL CRUD)
│   │   │   ├── alias_repository.py       # Entity alias operations
│   │   │   ├── entity_repository.py      # Entity CRUD and increment mentions
│   │   │   ├── event_repository.py       # Calendar event persistence
│   │   │   ├── relationship_repository.py # Graph edge/relationship operations
│   │   │   └── user_profile_repository.py # Preference database updates
│   │   │
│   │   ├── base.py             # Declarative SQLAlchemy Base class
│   │   ├── migrations.py       # Database schema initialization script
│   │   ├── models.py           # Relational schemas (ConversationModel, etc.)
│   │   └── session.py          # Async session maker connection wrapper
│   │
│   ├── models/                 # Validation Schemas
│   │   └── chat_models.py      # Request/Response Pydantic models
│   │
│   ├── prompts/                # Prompts templates directory
│   │   └── system_prompt.txt   # Base system prompt template instructions
│   │
│   ├── services/               # Core Services layer
│   │   ├── cognitive/          # Calendar and schedule timeline services
│   │   │   ├── duplicate_event_resolver.py # Overlap resolver
│   │   │   ├── event_extractor.py          # Event extraction engine
│   │   │   ├── event_update_detector.py    # Lifecycle update detector
│   │   │   ├── recurring_schedule_engine.py # Recurrence schedule occurrences calculator
│   │   │   ├── time_normalizer.py          # Relative UTC time normalizer
│   │   │   └── timeline_engine.py          # Timeline layout generator
│   │   │
│   │   ├── interfaces/         # Service Abstractions
│   │   │   └── base_chat_service.py # ChatService abstract interface
│   │   │
│   │   ├── llm/                # LLM Integration Layer
│   │   │   ├── base.py             # BaseLLM abstract interface
│   │   │   ├── factory.py          # LLMProviderFactory provider resolver
│   │   │   ├── generation_config.py # LLM Generation parameter configurations
│   │   │   ├── groq_provider.py    # Groq provider Responses wrapper
│   │   │   ├── openai_provider.py  # OpenAI provider Responses wrapper
│   │   │   └── placeholder.py      # Placeholder mock LLM response generator
│   │   │
│   │   ├── response/           # Intent and Validation pipeline
│   │   │   ├── intent_classifier.py  # Message intent classifier
│   │   │   ├── post_processor.py     # String clean-up processor
│   │   │   ├── prompt_builder.py     # System prompt dynamic assembly
│   │   │   ├── response_cache.py     # TTL-based response caching
│   │   │   └── response_validator.py # Fact-checking & length validation
│   │   │
│   │   ├── chat_service.py     # Main ChatService coordinator facade
│   │   ├── factory.py          # ServiceFactory DI registry
│   │   └── task_service.py     # TaskService lifecycle coordinator
│   │
│   ├── utils/                  # Helper modules
│   │   ├── file_loader.py      # Asynchronous file reading helpers
│   │   ├── helpers.py          # Time duration and tracking utils
│   │   └── logger.py           # Logging logger instantiator
│   │
│   └── main.py                 # FastAPI lifespan setup & entry point
│
├── docs/                       # Project Documentation System
│   ├── diagrams/               # Architecture Flowcharts (Mermaid)
│   │   ├── architecture.md
│   │   ├── backend_flow.md
│   │   ├── memory_flow.md
│   │   ├── providers.md
│   │   └── voice_flow.md
│   │
│   ├── phases/                 # Historical Phase records
│   │   ├── phase1.md
│   │   ├── phase2.md
│   │   ├── phase3.md
│   │   ├── phase4.md
│   │   ├── phase5.md
│   │   ├── phase6.md
│   │   ├── phase7.md
│   │   ├── phase8.md
│   │   ├── phase9.md
│   │   └── future.md
│   │
│   ├── api.md                  # API endpoints and interfaces
│   ├── architecture.md         # Layer specifications and ADR charts
│   ├── coding_guidelines.md    # Naming structures and standards
│   ├── folder_structure.md     # Directory structure handbook
│   ├── JARVIS_MASTER_CONTEXT.md # Onboarding master handbook
│   ├── roadmap.md              # Milestones progression roadmap
│   └── tech_stack.md           # Technologies and requirements lists
│
├── memory/                     # Conversation Memory layer
│   ├── base.py                 # BaseMemory abstract class
│   ├── base_memory.py          # Interface definitions
│   ├── chroma_repository.py    # Local ChromaDB vector storage repository
│   ├── conflict_resolver.py    # Memory conflict and duplicate detector
│   ├── decay_service.py        # Lifecycle aging & vector indexing retrier
│   ├── embedding.py            # SentenceTransformers wrapper service
│   ├── extractor.py            # Text fact extraction manager
│   ├── filter.py               # Memory persistence check filters
│   ├── in_memory.py            # Sliding history memory manager
│   ├── llm_extractor.py        # LLM-based fact extraction wrapper
│   ├── memory_factory.py       # Memory DI container
│   ├── memory_service.py       # SQLite & ChromaDB coordinate service
│   ├── repository.py           # Abstract BaseMemoryRepository definitions
│   ├── scorer.py               # Importance value calculator
│   ├── search.py               # SQL/Vector hybrid search service
│   ├── sqlite_repository.py    # SQLite dialogue log repository
│   ├── test_memory.py          # Memory verification tests
│   └── test_personality.py     # Personality constraint tests
│
├── tests/                      # Testing Framework Suite
│   └── cognitive/              # Integration and unit tests
│       ├── test_event_lifecycle.py # Calendar update & duplicate tests
│       ├── test_graph_engine.py    # Knowledge graph & alias tests
│       ├── test_habits_profile.py  # Habits and routines user profile tests
│       ├── test_recurrence_engine.py # Event recurrence calculations tests
│       ├── test_task_operations.py # Task lifecycle CRUD and transitions tests
│       └── test_temporal_engine.py # Event timeline database tests
│
├── voice/                      # Voice Interface module
│   ├── bin/                    # Standalone audio binaries (gitignored)
│   ├── models/                 # Audio ONNX model weights (gitignored)
│   ├── providers/              # STT and TTS Engines
│   │   ├── piper_provider.py   # Piper speech synthesizer
│   │   ├── stt_factory.py      # Speech-to-Text provider factory
│   │   ├── stt_provider.py     # Faster-Whisper transcriber
│   │   └── tts_factory.py      # Text-to-Speech provider factory
│   │
│   ├── config.py               # Voice interface configurations
│   ├── download_models.py      # Download models and binaries
│   ├── logger.py               # Voice-specific logging configuration
│   ├── microphone.py           # sounddevice audio PTT recorder
│   ├── session.py              # Voice conversation session manager
│   ├── test_voice.py           # Voice engine tests
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

## 2. Folder-by-Folder Specifications

### Directory: `app/api/v1/`
* **Purpose**: Hosts REST endpoint handlers.
* **Responsibilities**: Receives HTTP requests, validates Pydantic schemas, and routes execution to injected services.
* **Key Files**: `chat.py` (chat REST controller), `health.py` (health checks).
* **Dependencies**: `app/models/`, `app/services/factory.py`.

### Directory: `app/cognitive/`
* **Purpose**: Contains advanced multi-hop relational context reasoning.
* **Responsibilities**: Entity fuzzy aliasing, pronoun reference resolution, profile preference updates, and graph export visualizations.
* **Key Files**:
  * `resolution/alias_resolution_engine.py` (fuzzy name mapping).
  * `resolution/pronoun_resolver.py` (pronoun reference resolution).
  * `knowledge_graph/knowledge_graph_service.py` (main graph service facade).
  * `profile/user_profile_engine.py` (evolving user profile keys).
* **Dependencies**: `app/database/repositories/`, `app/cognitive/infrastructure/`, `app/services/llm/`.

### Directory: `app/database/`
* **Purpose**: Coordinates relational storage connections.
* **Responsibilities**: Exposing transactional operations and translating domain models to SQL queries.
* **Key Files**:
  * `models.py` (SQL tables declarations).
  * `session.py` (async transactional session maker).
  * `migrations.py` (automatic database schema initializations).
* **Dependencies**: `app/config/settings.py`.

### Directory: `app/services/`
* **Purpose**: Orchestrates central business logic.
* **Responsibilities**: Formatting prompts, validating answers, and parsing calendar schedules.
* **Key Files**:
  * `chat_service.py` (main conversation pipeline orchestrator).
  * `cognitive/timeline_engine.py` (calendar event viewer generator).
  * `response/prompt_builder.py` (dynamic prompt builder).
* **Dependencies**: `app/cognitive/`, `memory/`.

### Directory: `memory/`
* **Purpose**: Manages dialogue logs and vector similarity mappings.
* **Responsibilities**: Storing relational dialog turns, semantic indexing, and background aging tasks.
* **Key Files**:
  * `memory_service.py` (hierarchical recall coordinator).
  * `sqlite_repository.py` (direct SQL dialog logs repository).
  * `chroma_repository.py` (local vector embedding client).
* **Dependencies**: `app/database/repositories/`.

### Directory: `voice/`
* **Purpose**: Audio transcription and voice synthesis.
* **Responsibilities**: Captures local device microphone streams and manages sound playback threads.
* **Key Files**:
  * `microphone.py` (sounddevice listener).
  * `voice_service.py` (PTT pipeline orchestrator).
  * `download_models.py` (downloads Piper binary & Whisper weights).
* **Dependencies**: `app/services/factory.py`.
