# Conversational Memory Flow Diagram

* **Last Updated**: 2026-08-08
* **Current Phase**: Phase 5.3 (User Preferences, Habits & Tasks)
* **Status**: Freeze
* **Version**: v0.5.3

---

```mermaid
graph TD
    A[ChatRequest: message] --> B[Resolve Pronoun Referents via PronounResolver]
    B --> C[Query Hierarchical Contexts via MemoryService]
    
    subgraph Context Retrievals
        C1[UserProfileEngine: get_profile_context]
        C2[MemoryService: retrieve_long_term_context]
        C3[MemoryService: retrieve_semantic_context]
        C4[KnowledgeGraphService: expand_context]
        C5[TimelineEngine: generate_timeline]
        C6[TaskService: list_tasks]
    end
    
    C --> C1
    C --> C2
    C --> C3
    C --> C4
    C --> C5
    C --> C6
    
    C1 & C2 & C3 & C4 & C5 & C6 --> D[ContextBuilder: Token Budgeting]
    D --> E[Submit combined system prompt & history to LLM]
    E --> F[Receive LLM Result response]
    
    F --> G[Save User/Assistant logs to sliding Session History]
    G --> H[Trigger Async Background Save Tasks]
    
    subgraph Async Database Save & Indexing
        H1[save_exchange: Write logs to SQLite database]
        H2[save_exchange: Compute embeddings & index in ChromaDB]
    end
    
    subgraph Async Cognitive Extraction via BackgroundJobManager
        H3[Extract Graph entities & relationship edges to SQLite KG]
        H4[Evolve Profile preferences lists in SQLite Profiles]
        H5[Extract habits & routines in UserProfileEngine]
    end
    
    H --> H1
    H1 -->|Pending Index Status| H2
    H --> H3
    H --> H4
    H --> H5
```
