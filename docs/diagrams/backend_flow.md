# Backend Execution Sequence Diagram

* **Last Updated**: 2026-08-07
* **Current Phase**: Phase 5.3
* **Status**: Current
* **Version**: v0.5.2

---

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Router as API Router (chat.py)
    participant CS as ChatService
    participant MS as MemoryService
    participant CB as ContextBuilder
    participant LLM as GroqProvider
    participant Background as BackgroundJobManager

    Client->>Router: POST /chat (payload, session_id)
    activate Router
    Router->>CS: execute_chat(request)
    activate CS
    
    %% Context compilation
    CS->>MS: get_history(session_id)
    Note over CS: Resolves pronouns via PronounResolver
    CS->>MS: user_profile_engine.get_profile_context(session_id)
    CS->>MS: graph_service.expand_context(seed_entities)
    
    CS->>CB: build_context(profile, graph, semantic, timeline)
    CB-->>CS: returns budgeted context block
    
    CS->>LLM: generate_response(request, system_prompt, history)
    activate LLM
    LLM-->>CS: returns LLMResult (response text, tokens, latency)
    deactivate LLM
    
    %% Async background save pipeline
    CS->>MS: save_message(session_id, "user", message)
    activate MS
    MS->>Background: enqueue(extract_entities_and_profiles, message)
    MS-->>CS: returns save confirmation
    deactivate MS
    
    CS-->>Router: returns generated response text
    deactivate CS
    Router-->>Client: ChatResponse JSON payload
    deactivate Router
```
