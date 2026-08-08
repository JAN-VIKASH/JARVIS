# JARVIS Master Context - Developer Handbook

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 6 (Desktop Automation)
* **Next Phase**: Phase 7 (Browser Automation) [PLANNED]
* **Status**: Freeze
* **Version**: v0.6

---

## 1. Project Vision & Core Mandate

The mission of JARVIS is to establish a production-grade, local-first, low-latency personal AI assistant inspired by Tony Stark's hologram console helper. The system is designed to operate completely offline for voice interactions (STT/TTS) and metadata extraction, leveraging vector search (ChromaDB) and relational databases (SQLite) inside clean Repository and dependency injection boundaries.

---

## 2. Developer Onboarding Reading Order

When onboarding, new developers (and AI assistants) must read documents in this exact order to build a cohesive mental model:

```text
Project Vision & Vision History (JARVIS_MASTER_CONTEXT.md)
  │
  ▼
Roadmap (roadmap.md)
  │
  ▼
Architecture Details (architecture.md)
  │
  ▼
Workspace Directory Tree (folder_structure.md)
  │
  ▼
Coding Standards & Naming Conventions (coding_guidelines.md)
  │
  ▼
HTTP & Service Interfaces (api.md)
  │
  ▼
Current Phase Description (phases/phase6.md)
```

---

## 3. Startup & Initialization Sequence

The application initializes its services in the following order:

```text
1. Config Loading (app/config/settings.py loads .env parameters via Pydantic)
   │
   ▼
2. Logging Setup (app/config/logging.py configures console handlers and trace IDs)
   │
   ▼
3. Migrations Execution (app/database/migrations.py validates tables creation)
   │
   ▼
4. Repository Construction (Instantiates Entity, Edge, Profile, and Event Repositories)
   │
   ▼
5. Memory Layer Startup (Instantiates SQLite history repositories & ChromaDB vector clients)
   │
   ▼
6. Factories Injection (Resolves and caches class dependencies into ServiceFactory/MemoryFactory)
   │
   ▼
7. ChatService Setup (Injects LLM Providers, Memory Services, and ContextBuilder)
   │
   ▼
8. API Endpoints Up (FastAPI routing maps `/chat` and `/health`)
   │
   ▼
9. Voice Controller Initialized (PTT loop starts capturing microphone array loops)
```

---

## 4. Architectural Decision Records (ADR) Summary

Here is why core architectural choices were made:

* **Why Repository Pattern?** By abstracting direct SQL logic into Repository boundaries, the codebase is fully database-independent. JARVIS runs on SQLite locally, keeping installation simple.
* **Why Dependency Injection?** Constructor-based DI decouples class orchestration from instance configuration. In unit tests, expensive modules (LLM calls, databases, STT/TTS) are easily mocked by passing placeholder instances to constructors.
* **Why Service Factories?** Centralizes constructor call parameters, enforcing singleton lifetimes and resolving dependencies in a single registry module.
* **Why ChromaDB?** Local, file-persistent vector storage that runs offline, allowing JARVIS to run semantic similarity searches on past dialogue logs and timeline events without introducing subscription costs or internet latency.
* **Why Knowledge Graph?** Relational entity networking captures contextual relationships (e.g. "User uses Python", "Python is a programming language") that are easily missed by sliding short-term dialogue windows.
* **Why UserProfileEngine?** Maintains user preferences, skills, and configuration values, executing automated confidence decay and conflict resolution when new preferences emerge.
* **Why GraphReasoner?** Performs multi-hop BFS pathfinding algorithms to find indirect relationships (e.g. connecting User to a tool through a shared project).
* **Why BackgroundJobManager?** Text extraction (parsing entities, edges, profiles) requires separate LLM calls, adding several seconds of latency. Enqueuing these jobs onto background threads allows the chat system to reply to the user instantly.
* **Why ContextBuilder?** Prevents LLM context overflows by building prompts in priority order (User Profile -> Relational Facts -> Semantic Memory -> Graph Facts -> Timelines) and truncating once the character budget is reached.
* **Why TaskService?** Enforces lifecycle state machine transitions (pending, in_progress, completed, cancelled) and session boundaries, keeping the central ChatService orchestration clean.
* **Why RecurringScheduleEngine?** Decouples recurrence calculations (daily, weekly, monthly, weekday) from storage, enabling timelines to expand event ranges dynamically on-the-fly.
* **Why Habits in UserProfileEngine?** Reuses the profile engine to track recurring user preferences/habits without schema duplication, applying strict filters that ignore single occurrences.

---

## 5. Documentation Ownership Hierarchy

If discrepancies or contradictions occur across documentation files, resolve the conflict by giving authoritative weight in this order:

`Roadmap (roadmap.md) -> Master Context (JARVIS_MASTER_CONTEXT.md) -> Architecture (architecture.md) -> Folder Structure (folder_structure.md) -> Phase Docs (phases/*.md) -> API Reference (api.md) -> Diagrams`

---

## 6. Future Contributor & AI Workflow

### Contributor Workflow Loop
1. **Update Roadmap**: Adjust milestones and version indexes in `roadmap.md`.
2. **Update Core Context**: If changing layers or adding tools, update `architecture.md` and `JARVIS_MASTER_CONTEXT.md`.
3. **Register Factories**: Register any new services in `ServiceFactory` or `MemoryFactory` using constructor DI.
4. **Write Tests**: Add corresponding integration tests under `tests/cognitive/` or `tests/`.
5. **Verify Documentation**: Check that every new module, class, path, and method signature is synchronized with the current implementation.

### AI Assistant Contribution Guide
* **Review Mandate**: Before proposing any change, AI assistants must retrieve and review `Roadmap -> Master Context -> Architecture -> Current Phase -> Coding Guidelines -> Implementations` in that exact order.
* **No Speculations**: Never document planned features as completed. Mark any unimplemented proposals as `Planned` or `Next`.
* **Zero Code Modification in Documentation Steps**: During documentation freezes or synchronization tasks, do not modify source files or create new markdown documents.

---

## 7. Protected Core Modules (Must Never Be Broken)

The following interfaces describe the implemented architecture and must remain backward-compatible:
1. **The Provider Factories Contract**: All LLM, STT, and TTS engines must remain decoupled from specific vendors.
2. **REST Chat Scheme**: The inputs, outputs, and validation rules of `/chat` must remain stable.
3. **Base Interface Signatures**: Do not change parameters of `BaseLLM`, `BaseMemory`, `BaseSTT`, `BaseTTS`, or `BaseChatService`.
4. **Offline Capability & Cache Only**: Voice and Embedding services must always remain local-first. SentenceTransformers must load *only* from the local cache (`local_files_only=True`). Raise a clear error if missing, prompting the user to run `python -m voice.download_models`.
5. **SOLID Repository Pattern Separation**: Relational logic and query compiling code must stay inside repositories, never leaking SQLAlchemy details to `MemoryService` or `ChatService`.
6. **Task Lifecycle & Isolation**: Task updates, status transitions, and queries must remain isolated by `session_id`, and invalid status transitions must be blocked by the `TaskService` validation layer.

---

## 8. Documentation Scope

* **Core Horizon**: This documentation reflects the implementation state up to the completion of Phase 5.3.
* **Synchronization Mandate**: All developer documentation must remain synchronized with the current implementation.
* **Future Feature Rules**: Any features implemented after Phase 5.3 (such as Phase 6 desktop control) require corresponding documentation upgrades before being marked as complete.
* **Planned Separations**: Planned or experimental features must remain clearly separated from completed modules.
* **Authoritative Reference**: This documentation is designed to be the primary reference manual for developers and future AI assistants.

---

## 9. Documentation Maintenance Policy

Whenever implementation changes occur, the following documents must be updated where applicable to ensure ongoing accuracy:
* [roadmap.md](roadmap.md)
* [architecture.md](architecture.md)
* [folder_structure.md](folder_structure.md)
* [api.md](api.md)
* [coding_guidelines.md](coding_guidelines.md)
* [JARVIS_MASTER_CONTEXT.md](JARVIS_MASTER_CONTEXT.md)
* Architectural Diagrams under `docs/diagrams/`
* Corresponding Phase logs under `docs/phases/`

Documentation upgrades are considered an essential component of feature completion. No feature is considered complete until both implementation code and documentation files have been fully synchronized.
