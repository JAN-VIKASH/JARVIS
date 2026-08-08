# JARVIS Coding Guidelines

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 5.3 (User Preferences, Habits & Tasks)
* **Next Phase**: Phase 6 (Desktop Automation) [PLANNED]
* **Status**: Freeze
* **Version**: v0.5.3

---

This document outlines the coding practices, naming standards, and architectural constraints required for contributing to the JARVIS project.

## 1. Naming Conventions

All modules, classes, and tests must adhere to these structural prefix/suffix naming conventions:

* **Services**: Suffix with `Service` (e.g. `ChatService`, `MemoryService`).
* **Repositories**: Suffix with `Repository` (e.g. `EntityRepository`, `EventRepository`).
* **Factories**: Suffix with `Factory` (e.g. `ServiceFactory`, `MemoryFactory`, `stt_factory`).
* **Interfaces**: Prefix with `Base` (e.g. `BaseLLM`, `BaseSTT`, `BaseChatService`).
* **Models**: Suffix with `Model` for SQLAlchemy ORM schemas (e.g. `EntityModel`, `UserProfileModel`).
* **Providers**: Suffix with `Provider` for third-party connector adapters (e.g. `GroqProvider`, `OpenAIProvider`).
* **Utilities**: Group helper logic in files suffixed with `_utils.py` or submodules representing structural logic (e.g. `time_normalizer.py`).
* **Tests**: Prefix test files with `test_` and test class cases with `Test` (e.g. `tests/cognitive/test_graph_engine.py` -> `TestGraphEngine`).
* **Configuration Modules**: Save configurations in files suffixed with `_config.py` or inside `app/config/settings.py`.

---

## 2. Layering & Architectural Mandates

### Dependency Direction Rule
Data and method invocations must only flow downwards:
`Presentation -> API -> Service -> Cognitive -> Memory -> Repositories -> Storage -> Infrastructure`
* Upward imports or database calls bypassing the Repository layer are strictly forbidden.
* Business services (like `ChatService`) must never depend on concrete provider models. Depend only on base interfaces (`BaseLLM`) resolved via DI.

### Constructor-Based Dependency Injection (DI)
All dependencies must be declared in constructor parameters (`__init__`) and resolved lazily via cached factory getters:

```python
# Mandate: Injected constructor parameters
class ChatService(BaseChatService):
    def __init__(self, llm: BaseLLM, memory_service: MemoryService):
        self.llm = llm
        self.memory_service = memory_service
```

> [!NOTE]
> **Architectural Decision Record: Constructor DI**
> By forcing dependencies to be passed via parameters during construction, we isolate dependencies. Developers can easily write mocks for unit tests without needing complex monkeypatching of global modules.

---

## 3. Database & Memory Persistence Guidelines

### Repository Pattern & Transactions
* Direct SQL execution (e.g. `session.execute(stmt)`) inside business services is forbidden. Place all queries inside repository files in `app/database/repositories/`.
* Modifications and deletions must run within transaction contexts. In case of exceptions, transactions must automatically roll back.
* **SQLAlchemy Session Model Refresh**: After session commits (`await session.commit()`), always refresh instance properties using `await session.refresh(model)` to avoid `MissingGreenlet` exceptions when reading database-generated defaults (like timestamp columns).
* **Session Isolation Mandate**: Any query or persistent update to tasks/events must enforce isolation filtering by a mandatory `session_id` to prevent cross-session leaks.
* **Lifecycle Transition Validation**: All task status changes must proceed through the `TaskService` transition state machine. Raw updates bypassing transition checks are prohibited.
* **Asynchronous Migration Safety**: Database upgrades or column alterations on startup must execute asynchronously checking column presence via `PRAGMA table_info` rather than raw synchronous cursor blocks.

### Cache Management & Invalidation
* Cache expensive, repeated lookups (like entity aliases or multi-hop pathfinders) using bounded async-safe LRU caching decorators.
* Mutative actions (such as adding, updating, or deleting nodes/relationships, or updating tasks/habits) must trigger explicit cache invalidation to prevent stale reads.

---

## 4. Asynchronous & Background Processing

### Async Event Loop Integrity
* Never execute blocking IO or CPU-bound calls (speech transcription, TTS synthesis process executables, heavy matrix calculations) in the async loop thread.
* Offload blocking operations using thread executors:
  ```python
  loop = asyncio.get_running_loop()
  result = await loop.run_in_executor(None, blocking_func, *args)
  ```

### Background Extraction Workers
* Run non-blocking text extraction operations (parsing entities, edges, profiles) asynchronously using the `BackgroundJobManager` queue loop, shielding conversational reply flows from extraction latencies.

---

## 5. Testing & Verification Philosophy

* **Unit Tests**: Test logic in isolation using mocked providers (like `MockLLM` returning preloaded mock JSON strings).
* **Integration Tests**: Verify database pipelines, optimistic version locking, cache invalidations, and temporal event extractions.
* **Repository Deletion Safety**: Tests that perform entity deletions must verify that related aliased routes or edge connections are re-pointed or safely pruned without causing SQL orphan constraints.

---

## 6. Rules for Adding Future Modules (Phase 5.3 Onwards)

Whenever adding a new phase component:
1. **Update Roadmap**: Shift sprint statuses (Completed -> Current -> Planned) in `roadmap.md`.
2. **Inherit Base Classes**: Build adapters inheriting from base abstract classes.
3. **Register in Factories**: Place instantiations inside factories (`MemoryFactory`, `ServiceFactory`).
4. **Update Handbook**: Document change logs, folder specs, and configuration schemas.

---

## 7. Documentation Validation Checklist

To maintain synchronization across all modules, future contributors must verify these checklist items:
* [ ] Every documented class and class name is synchronized with the current implementation.
* [ ] Every documented service, repository, and provider exists in its designated directory.
* [ ] Every documented public API endpoint route and parameter is updated to reflect the current implementation.
* [ ] Every Mermaid flow, sequence, or class diagram describes the implemented architecture.
* [ ] No future placeholder features are documented as "Completed" or "Current".
* [ ] Terminology remains consistent throughout all documents (e.g. `is_voice` flag parameter definitions).
* [ ] No markdown files outside the authoritative paths contain conflicting roadmaps or architecture parameters.

