# Phase 4: Long-Term Memory (SQLite + ChromaDB)

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 5.2 (Knowledge Graph, User Profiles & Relational Memory)
* **Next Phase**: Phase 5.3 (User Preferences, Habits & Tasks) [PLANNED]
* **Status**: Completed
* **Version**: v0.4

---

## Objectives
Build a production-grade, modular Long-Term Memory system that persists conversations, user facts, preferences, goals, notes, and semantic memories across application restarts. Decouple components using repository abstractions to ensure the design is ready for future PostgreSQL migration.

## Problem Solved
Allowing JARVIS to remember context beyond a sliding window of recent short-term messages, indexing conversational facts relational-first (to query properties) and vector-second (to enable semantic lookup).

## Change Log
* **Added**:
  * `app/database/base.py` & `session.py`: Declarative ORM base configuration and session makers.
  * `app/database/models.py`: Declarative tables tracking conversations, facts, goals, and notes.
  * `app/database/migrations.py`: Migrations layer running tables validation.
  * `memory/repository.py`: Base repository interface contract.
  * `memory/sqlite_repository.py`: Relational async memory persistence implementation.
  * `memory/chroma_repository.py`: Vector space persistence implementation.
  * `memory/filter.py`: Evaluator checking semantic validity to prevent small-talk noise indexing.
  * `memory/extractor.py`: Deterministic parser pulling keys and categories from text turns.
  * `memory/scorer.py`: Importance ranker scoring records (0 to 100).
  * `memory/embedding.py`: local Hugging Face embedding calculations.
  * `memory/search.py`: Similarity vector query runner.
  * `memory/memory_service.py`: Memory service coordinator.
  * `memory/memory_factory.py`: Dependency Injection container.
  * `memory/test_memory.py`: Tests runner validating database layers.
* **Modified**:
  * `app/config/settings.py`: Default database configurations setup.
  * `app/services/factory.py` & `chat_service.py`: Resolving memory via factory and formatting system prompts with retrieved context.
  * `voice/download_models.py`: Cache Hugging Face models offline.

## Architecture
```text
      User message
           │
           ├── (Read) Search ChromaDB (semantic lookup) ──> Context string
           │                                                    │
           ├── (Read) Retrieve Recent Short-Term History        │ (Inject Context)
           │                                                    v
           v                                            [ ChatService ]
      System Prompt + Context + Deque History ────────> Call LLM Provider
           │                                                    │
           v                                                    v
      LLM response ──────────────────────────────────> Return response to User
           │
           └── Asynchronous Task (create_task)
                 ├── MemoryFilter.should_persist() -> True
                 ├── Extract facts, preference keys, goals, notes
                 ├── Update existing rows if duplicates matched
                 └── Embed doc string & index in ChromaDB
```

## Verification
* Run local memory validation verification:
  ```bash
  venv\Scripts\python -m unittest memory.test_memory
  ```

## Known Limitations
* The inclusion of local PyTorch and transformers increases storage foot-print.

## Future Improvements
* Set up remote PostgreSQL and Qdrant servers.

---

# Phase 4.1: Advanced Long-Term Memory Improvements (v0.4.1)

## Objectives
Introduce a hybrid memory extraction pipeline, entity versioning with optimistic lock deactivation, importance-based memory decay with reversible archiving, multi-factor weighted retrieval scoring, a 4-layer context memory hierarchy, and transactional database-first consistency rules.

## Problem Solved
Enforcing data-consistency (relational committed first, vector second) and implementing confidence decaying and conflict-resolution rules so that old facts are deactivated when new ones are learned.

## Change Log
* **Added**:
  * `app/database/upgrade.py`: Isolated migration scripts.
  * `memory/llm_extractor.py`: LLM-driven fallback parser.
  * `memory/conflict_resolver.py`: Resolves unique conflict overlaps.
  * `memory/decay_service.py`: Background worker tracking decay ticks.
* **Modified**:
  * `app/config/settings.py`: Added rankings and decay thresholds configs.
  * `app/database/models.py`: Appended version and lifecycle columns.
  * `memory/search.py`: Rebuilt to support multi-factor scoring.
  * `memory/memory_service.py`: Offloaded DB writes to async tasks.
  * `app/services/chat_service.py`: Configured 4-layer prompt contexts.
  * `app/main.py` & `voice/voice_service.py`: Shutdown hooks mapping.
  * `memory/test_memory.py`: Appended testing parameters.

## Lessons Carried Into Next Phase
* Flat facts are not enough. JARVIS needs time-awareness (calendar engine) and entities networking (knowledge graph links) to reason structurally.


