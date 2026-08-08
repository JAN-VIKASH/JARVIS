# JARVIS Roadmap

* **Last Updated**: 2026-08-08
* **Latest Completed Phase**: Phase 5.3 (User Preferences, Habits & Tasks)
* **Next Phase**: Phase 6 (Desktop Automation)
* **Status**: Freeze
* **Version**: v0.5.3

---

## Development Milestones

```text
[✅ Phase 1: Foundation] ──> [✅ Phase 2: Groq LLM] ──> [✅ Phase 3: Voice PTT]
                                                                │
                                                                v
[Planned Phase 7: Browser] <── [⚡ Next Phase 6: Desktop] <── [✅ Phase 5.3: Habits & Tasks] <── [✅ Phase 5.2: Relational Graph] <── [✅ Phase 5.1.1: Event Lifecycle] <── [✅ Phase 5.1: Event Engine] <── [✅ Phase 4: Long Memory]
```

---

## Detailed Phase Outline

### ✅ Phase 1: Backend Foundation (v0.1)
* **Goal**: Establish core system pipeline, validation logic, configurations, and API controllers.
* **Features**:
  * FastAPI routing server.
  * Pydantic Settings env loader.
  * Central logger and exception handler mappings.
  * Thread-safe memory sliding context storage.
  * Placeholder mockup provider.

### ✅ Phase 2: Groq Integration (v0.2)
* **Goal**: Switch active LLM engine to Groq.
* **Features**:
  * Official async `groq` SDK integration.
  * Dynamic LLMProviderFactory configuration mapping.
  * Telemetry reporting for input, output, total token calculations and latency.
  * Error handling and exponential retry backoff.

### ✅ Phase 3: Voice Interface (v0.3)
* **Goal**: Local offline audio synthesis and speech-to-text.
* **Features**:
  * Speech-to-Text via Faster-Whisper (CPU run).
  * Text-to-Speech via Piper standalone binary executor.
  * Asynchronous non-blocking playback threads.
  * Keystroke-based Push-to-Talk recorder.
  * Modular `stt_factory` and `tts_factory` registries.
  * Decoupled service layer (`BaseChatService` and `ServiceFactory` context).

### ✅ Phase 4: Long-Term Memory (v0.4)
* **Goal**: Persist conversations, user profile facts, preferences, goals, notes, and tasks across restart cycles.
* **Features**:
  * Persistent storage using SQLite and SQLAlchemy 2.0 Async ORM.
  * Semantic vector similarity query lookups via a local ChromaDB PersistentClient.
  * Local, offline-enforced Hugging Face `SentenceTransformers` embeddings.
  * Memory filtering rules to block greeting and casual talk noise.
  * Asynchronous non-blocking background index/write tasks.

### ✅ Phase 4.1: Advanced Memory Improvements (v0.4.1)
* **Goal**: Implement hybrid extraction fallback, optimistic concurrency control, importance-based aging/decay, weighted retrieval scoring, and a 4-layer memory hierarchy.
* **Features**:
  * Hybrid Extraction Pipeline: Combines fast deterministic regex matcher with LLMMemoryExtractor fallback.
  * Versioning & Optimistic Locking: Automatic entity versioning and deactivation of older single-value records.
  * Aging & Reversible Archiving: Importance-based memory decay with keyword query reactivation.
  * Weighted Retrieval Ranking: Incorporates similarity (0.40), importance (0.20), confidence (0.15), recency (0.15), and frequency (0.10).
  * 4-Layer Context Assembly: Segmented LLM prompt insertion (Current Turn -> Session History -> SQL Long-Term -> Vector Semantic).
  * Transaction Consistency & Idempotent Retry Loop: SQLite committed first, with background vector index retries upon failures.

### ✅ Phase 5.1: Temporal Reasoning & Event Engine (v0.5.1)
* **Goal**: Track, extract, and display dynamic calendar events, deadlines, milestones, and timelines.
* **Features**:
  * Time Normalizer parser resolving relative temporal phrases (e.g. "tomorrow at 5pm") into UTC timestamps.
  * LLM-driven Event Extractor parsing events from user utterances.
  * EventRepository for database persistence of calendar schedules.
  * TimelineEngine yielding timeline feeds (daily, weekly, monthly, upcoming, project status, overdue).

### ✅ Phase 5.1.1: Event Lifecycle & Timeline Intelligence (v0.5.1.1)
* **Goal**: Implement robust event update tracking, lifecycle status, duplicate checking, and vector event search.
* **Features**:
  * Lifecycle state machine (`planned`, `completed`, `postponed`, `cancelled`).
  * Deduplication engine automatically matching overlapping events.
  * Copy-On-Write historical versions of event models.
  * ChromaDB vector indexing of events enabling semantic schedule queries.

### ✅ Phase 5.2: Knowledge Graph, User Profiles & Relational Memory (v0.5.2)
* **Goal**: Implement entity/relationship extraction, structured user profiles, alias resolution, and multi-hop graph reasoning.
* **Features**:
  * Persistent SQLite Knowledge Graph (`entities`, `relationships`, `entity_aliases`, `entity_merge_audits`).
  * Alias Resolution Engine handling exact, normalized, and fuzzy edit-distance match mappings.
  * Pronoun Resolution resolving referents from recent dialog histories.
  * Dynamic User Profile Engine tracking and updating user preference structures.
  * Graph Exporter & Importer backing up states to JSON, DOT, and GraphML files.
  * Graph Statistics engine computing network metrics.
  * Multi-hop GraphReasoner tracing chain linkages.
  * Token-budgeted ContextBuilder compiling ranked contexts.

### ✅ Phase 5.3: User Preferences, Habits & Tasks (v0.5.3)
* **Goal**: Extract user habits/routines, compute recurring events, and manage task lists with lifecycle state machines.
* **Features**:
  - Dedicated Task Service with session isolation, derived flags (overdue, upcoming), and lifecycle transition checking.
  - User habits and routines profile engine ignoring isolated event extractions.
  - Recurring schedule engine resolving daily, weekly, weekday, and monthly (with overflow day support) occurrences.
  - Temporal timelines expansion integrating recurring occurrences on-the-fly.

---

## Future Roadmap

### ⚡ Next Phase 6: Desktop Automation (v0.6) [PLANNED]
* **Goal**: OS desktop navigation.
* **Details**: Run GUI-level operations, control mouse, keyboard, and automate administrative tasks.

### Phase 7: Browser Automation (v0.7) [PLANNED]
* **Goal**: Browser scraping and UI interactions.
* **Details**: Integrate Playwright to navigate websites, complete checkouts, and pull dynamic HTML assets.

### Phase 8: Vision (v0.8) [PLANNED]
* **Goal**: OCR and image interpretation.
* **Details**: Local image processing pipelines via ONNX models to analyze screen snapshots.

### Phase 9: Wake Word (v0.9) [PLANNED]
* **Goal**: Continuously listening hotword service.
* **Details**: Add background thread audio processing to capture wake trigger phrase ("Hey Jarvis") using local, lightweight engine.

### Phase 10: Desktop Graphical User Interface (v1.0) [PLANNED]
* **Goal**: Stunning visual HUD.
* **Details**: Create clean desktop panel (using electron or Tauri) showing agent status and chat records.

### Phase 11: Multi-Agent System (v1.1) [PLANNED]
* **Goal**: Task division among subagents.
* **Details**: Orchestrate specialized subagents to tackle complex workflows parallelly.

### Phase 12: Cloud Sync (v1.2) [PLANNED]
* **Goal**: Secured database and state synchronization across multiple user machines.
