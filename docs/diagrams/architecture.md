# Architecture Layers Diagram

* **Last Updated**: 2026-08-08
* **Current Phase**: Phase 5.3 (User Preferences, Habits & Tasks)
* **Status**: Freeze
* **Version**: v0.5.3

---

```mermaid
graph TD
    %% Presentation Layer
    subgraph Presentation Layer
        CLI[PTT CLI Console]
        %% GUI[Desktop GUI HUD - Planned Phase 10]
    end

    %% API Layer
    subgraph API Layer
        REST[FastAPI chat router - chat.py]
    end

    %% Service Layer
    subgraph Service Layer
        Factory[ServiceFactory]
        CS[ChatService]
        VS[VoiceService]
        MS[MemoryService]
        TS[TaskService]
    end

    %% Cognitive Layer
    subgraph Cognitive Layer
        KG[KnowledgeGraphService]
        UP[UserProfileEngine]
        AR[AliasResolutionEngine]
        PR[PronounResolver]
        CB[ContextBuilder]
        TE[TimelineEngine]
        RSE[RecurringScheduleEngine]
    end

    %% Core Implementations
    subgraph Engines / Providers
        LLM[BaseLLM / GroqProvider]
        STT[BaseSTT / FasterWhisperSTT]
        TTS[BaseTTS / PiperTTS]
    end

    %% Repositories / Storage
    subgraph Storage / DB Layer
        SQL[SQLite Database]
        Chroma[ChromaDB Vector Indexes]
    end

    %% Hardware Layer
    subgraph Hardware Layer
        Mic[Microphone Input]
        Spk[Speaker Output]
    end

    %% Connections
    CLI --> VS
    REST --> CS
    
    Factory -->|Resolves| CS
    Factory -->|Resolves| TS
    VS -->|Injects| STT
    VS -->|Injects| TTS
    VS -->|Injects| CS
    
    CS --> LLM
    CS --> MS
    CS --> CB
    CS --> TS
    CS --> TE
    
    MS --> KG
    MS --> UP
    MS --> AR
    MS --> PR
    
    TE --> RSE
    TE --> SQL
    TS --> SQL
    KG --> SQL
    KG --> Chroma
    UP --> SQL
    AR --> SQL
    
    VS -->|Captures| Mic
    TTS -->|Plays| Spk
```

> [!NOTE]
> **Planned GUI Integration (Phase 10)**:
> A Desktop Graphical User Interface (HUD) is planned for Phase 10. It will connect to the API Layer (`REST`) but is not part of the active Phase 5.2 execution path.
