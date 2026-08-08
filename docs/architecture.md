# JARVIS Architecture Details

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

## 1. Architectural Layers & Communication Rules

JARVIS is built upon a strict, unidirectional layered architecture. Data and calls flow downwards through the layers. High-level layers must never depend on low-level implementation details, and low-level layers are forbidden from initiating calls to higher-level layers.

```text
  +-------------------------------------------------------------+
  | Presentation Layer: PTT CLI Console / Web Interface         |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | API Layer: FastAPI Router Endpoints (chat.py, health.py)    |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | Service Layer: Facade Orchestrators (ChatService, VoiceSvc) |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | Cognitive Layer: UserProfile, Graph, Alias, Pronouns        |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | Memory / Repository Layer: Entity, Relational, Event repos  |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | Storage Layer: SQLite (SQLAlchemy 2.0 Async), ChromaDB      |
  +------------------------------┬------------------------------+
                                 │
                                 v
  +-------------------------------------------------------------+
  | Infrastructure Layer: BackgroundJobManager, Exceptions      |
  +-------------------------------------------------------------+
```

### Allowed Dependency Directions
* **Presentation Layer** can depend on **Service Layer** and **API Layer**.
* **API Layer** can depend **only** on **Service Layer** abstractions (BaseChatService).
* **Service Layer** depends on **Cognitive Layer** engines, **LLM Layer** providers, and **Memory Layer** repositories.
* **Cognitive Layer** depends on **Memory/Repository Layer** and **Infrastructure Layer**.
* **Repository Layer** depends on **Storage Layer** data structures (SQLAlchemy Models, Chroma Client).

### Forbidden Dependency Mappings ❌
* **No Database/SQL leaking**: Service Layer and API Layer must never import `get_async_session`, SQLAlchemy models, or ChromaDB dependencies. All database calls must be brokered by repositories.
* **No upward callbacks**: Repositories can never import services or routers.
* **No direct Presentation-to-DB calls**: The Presentation layer (e.g. `VoiceController`) cannot query repositories directly.

---

## 2. Layer Specifications

### Layer 1: Presentation Layer
* **Why it exists**: Provides an interactive interface for human operations.
* **Responsibilities**: Captures user microphone buffers, detects push-to-talk keystrokes, and outputs synthesized audio.
* **Ownership**: CLI console controllers.
* **Dependencies**: `VoiceService`, `ChatRequest`, `BaseChatService`.
* **Communication Rules**: Invokes VoiceService methods synchronously on user input actions.

### Layer 2: API Layer
* **Why it exists**: Exposes REST interfaces for external clients or desktop GUI containers.
* **Responsibilities**: Input validation schema assertions, correlation ID mappings, and request timing telemetry.
* **Ownership**: FastAPI API routers (`app/api/v1/`).
* **Dependencies**: Pydantic schemas, `BaseChatService`, `ServiceFactory`.
* **Communication Rules**: Receives HTTP request, resolves `ChatService` from factory, executes chat, returns response.

### Layer 3: Service Layer
* **Why it exists**: Serves as the central coordinator for business logic pipelines.
* **Responsibilities**: Retrieves conversation state, budgets contexts, invokes LLM inference, and enqueues async persistence updates.
* **Ownership**: Core Services (`app/services/`).
* **Dependencies**: `BaseLLM`, `MemoryService`, `ContextBuilder`, `BackgroundJobManager`.
* **Communication Rules**: Orchestrates pipeline flows asynchronously without blocking execution threads.

### Layer 4: Cognitive Layer
* **Why it exists**: Implements human-centric logic (identity profiles, aliases, references, event statuses).
* **Responsibilities**: Evolving preferences, resolving fuzzy aliases, timeline scheduling, and multi-hop reasoning.
* **Ownership**: Cognitive engines (`app/cognitive/`).
* **Dependencies**: Database repositories, `BackgroundJobManager`, `BaseLLM`.
* **Communication Rules**: Invoked by Memory/Chat services, queries repositories, performs algorithms, and writes parameters.

### Layer 5: Memory / Repository Layer
* **Why it exists**: Decouples business rules from physical database drivers.
* **Responsibilities**: Translates domain operations into database transactions (SQL queries, Chroma mappings).
* **Ownership**: Repositories (`app/database/repositories/`).
* **Dependencies**: SQLAlchemy async sessions, models.
* **Communication Rules**: Enforces atomicity, rolls back database transactions on SQL failures, and runs refresh procedures.

### Layer 6: Storage Layer
* **Why it exists**: Holds persistent and semantic vector databases.
* **Responsibilities**: Persisting binary files, running indexing, and parsing schema models.
* **Ownership**: SQLAlchemy and Chroma DB wrappers.
* **Dependencies**: `aiosqlite`, `chromadb`, local `SentenceTransformers`.

### Layer 7: Infrastructure Layer
* **Why it exists**: Provides cross-cutting platform facilities.
* **Responsibilities**: Thread execution queues (`BackgroundJobManager`), custom exceptions (`exceptions.py`), and correlation middlewares.

---

## 3. Architectural Decision Records (ADR)

> [!NOTE]
> **ADR 1: Repository Pattern for Database Isolation**
> * **Context**: JARVIS needs relational persistence (SQLite locally) but must be prepared to scale to production databases (PostgreSQL) without code rewrites.
> * **Decision**: Mandate the Repository Pattern. All SQL querying must live inside classes in `app/database/repositories/`. Services call these classes; swapping databases only requires creating a new repository implementation.

> [!NOTE]
> **ADR 2: Constructor-Based Dependency Injection (DI)**
> * **Context**: Unit testing services requires mocking heavy LLM, STT/TTS, and database calls to prevent network latency and side-effects.
> * **Decision**: Enforce constructor-based DI. All class dependency parameters are injected during construction. Singleton factories (`ServiceFactory`, `MemoryFactory`) instantiate and cache these objects, separating construct logic from execution logic.

> [!NOTE]
> **ADR 3: BackgroundJobManager for Asynchronous Extractions**
> * **Context**: Parsing entities, links, and user profiles from messages requires secondary LLM invocations, adding 2–4 seconds of latency.
> * **Decision**: Implement `BackgroundJobManager`. The main response returns to the user immediately, and extraction jobs are enqueued to a background task worker thread.

> [!NOTE]
> **ADR 4: Token-Budgeted ContextBuilder**
> * **Context**: Combining profiles, relationships, events, and semantic memories can easily exceed Groq's token limits, causing requests to fail.
> * **Decision**: ContextBuilder. It aggregates strings in priority order (Profile > Relational Facts > Semantic Memory > Graph Facts > Timelines) and stops accumulating once a token threshold (e.g. 4000 tokens) is met.

> [!NOTE]
> **ADR 5: Knowledge Graph & User Profiles**
> * **Context**: Standard chat history fails to capture the relationship between entities (e.g., "Mr Stark uses Python") or remember long-term user preferences.
> * **Decision**: Introduce a persistent SQLite Knowledge Graph combined with a UserProfileEngine. This allows JARVIS to map user preferences, career goals, and tool usages structurally.

> [!NOTE]
> **ADR 6: GraphReasoner & Multi-Hop Pathfinding**
> * **Context**: Cognitive contexts often require following relationships across multiple nodes (e.g. "User works on ResearchHub" + "ResearchHub uses Python" => "User uses Python").
> * **Decision**: GraphReasoner. It computes paths up to depth 3 to build logical inferences.

> [!NOTE]
> **ADR 7: Layered Context Retrieval**
> * **Context**: Prioritizing context insertion is essential for LLM focus.
> * **Decision**: Enforce a 4-layer memory context retrieval sequence: Layer 1 (Current Input) -> Layer 2 (Sliding History turns) -> Layer 3 (SQL Relational Profile data) -> Layer 4 (Vector Semantic database exchanges).


