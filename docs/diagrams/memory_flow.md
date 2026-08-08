# Conversational Memory Flow Diagram

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

```mermaid
graph TD
    A[ChatRequest: message] --> B[Resolve Pronoun Referents]
    B --> C[Query Hierarchical Contexts]
    
    subgraph Context Retrievals
        C1[UserProfileEngine: get_profile_context]
        C2[SQLiteRepo: retrieve_long_term_context]
        C3[ChromaRepo: retrieve_semantic_context]
        C4[KnowledgeGraphService: expand_context]
        C5[TimelineEngine: generate_timeline]
    end
    
    C --> C1
    C --> C2
    C --> C3
    C --> C4
    C --> C5
    
    C1 & C2 & C3 & C4 & C5 --> D[ContextBuilder: Token Budgeting]
    D --> E[Submit combined prompt list to LLM]
    E --> F[Receive LLM Result response]
    
    F --> G[Save User/Assistant logs to SQLite]
    G --> H[BackgroundJobManager: Enqueue Extraction Jobs]
    
    subgraph Async Background Tasks
        H1[Extract Graph entities & relationship edges]
        H2[Evolve Profile preferences lists]
        H3[Index Vector Embeddings in ChromaDB]
    end
    
    H --> H1 & H2 & H3
```

