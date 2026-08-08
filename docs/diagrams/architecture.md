# Architecture Layers Diagram

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

```mermaid
graph TD
    %% Presentation Layer
    subgraph Presentation Layer
        CLI[PTT CLI Console]
        GUI[Desktop GUI]
    end

    %% API Layer
    subgraph API Layer
        REST[FastAPI api/v1/chat.py]
    end

    %% Service Layer
    subgraph Service Layer
        Factory[ServiceFactory]
        CS[ChatService]
        VS[VoiceService]
        MS[MemoryService]
    end

    %% Cognitive Layer
    subgraph Cognitive Layer
        KG[KnowledgeGraphService]
        UP[UserProfileEngine]
        AR[AliasResolutionEngine]
        PR[PronounResolver]
        CB[ContextBuilder]
    end

    %% Core Implementations
    subgraph Engines / Providers
        LLM[BaseLLM / GroqProvider]
        STT[BaseSTT / FasterWhisperSTT]
        TTS[BaseTTS / PiperTTS]
    end

    %% Repositories / Storage
    subgraph Storage / DB Layer
        SQL[SQLite / PostgreSQL]
        Chroma[ChromaDB Vector Indexes]
    end

    %% Hardware Layer
    subgraph Hardware Layer
        Mic[Microphone Input]
        Spk[Speaker Output]
    end

    %% Connections
    CLI --> VS
    GUI --> REST
    REST --> CS
    
    Factory -->|Resolves| CS
    VS -->|Injects| STT
    VS -->|Injects| TTS
    VS -->|Injects| CS
    
    CS --> LLM
    CS --> MS
    CS --> CB
    
    MS --> KG
    MS --> UP
    MS --> AR
    MS --> PR
    
    KG --> SQL
    KG --> Chroma
    UP --> SQL
    AR --> SQL
    
    VS -->|Captures| Mic
    TTS -->|Plays| Spk
```

