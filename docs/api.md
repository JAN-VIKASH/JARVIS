# JARVIS API & Service Interfaces Reference Manual - Phase 5.2 Freeze

This document describes the external HTTP API endpoints and the internal service interfaces implemented up to Phase 5.2.

---

## Part 1: External HTTP API Reference

All HTTP routes are versioned and can be accessed with the prefix `/api/v1`.

### 1. System Health Check
* **Purpose**: Returns the health status of the application.
* **URL Paths**: `/health`, `/api/v1/health`
* **Method**: `GET`
* **Authentication**: None
* **Input**: None.
* **Output**: A JSON payload returning status and the identifier name.
* **Validation**: None.
* **Errors**: `500 Internal Server Error` if backend server fails.
* **Internal Execution Flow**: API Router -> resolves status directly -> returns status payload.

#### Response Example (`200 OK`)
```json
{
  "status": "ok",
  "assistant": "Jarvis"
}
```

### 2. Chat Interaction
* **Purpose**: Processes text queries and computes synthesized speech constraint lengths.
* **URL Paths**: `/chat`, `/api/v1/chat`
* **Method**: `POST`
* **Request Format**: `application/json`
* **Response Format**: `application/json`
* **Input Parameters**:
  * `message` (string, required): The query text to process.
  * `session_id` (string, optional, defaults to `"default"`).
  * `is_voice` (boolean, optional, defaults to `false`): Restricts response word limits for TTS.
* **Validation**: Standard FastAPI Pydantic schema validation. Enforces `message` string min_length = 1.
* **Errors**:
  * `422 Unprocessable Entity`: Validation failure on request payload parameters.
  * `502 Bad Gateway`: groq/LLM service connectivity error.
  * `500 Internal Server Error`: SQLite or filesystem crashes.
* **Internal Execution Flow**: 
  1. API Router receives payload.
  2. Resolves `ChatService` from `ServiceFactory`.
  3. Invokes `ChatService.execute_chat(request)`.
  4. ChatService queries memory contexts, builds budgeted prompt using `ContextBuilder`, and queries the active LLM provider.
  5. ChatService saves records to `MemoryService` and returns the generated string.

#### Request Body Schema (`ChatRequest`)
```json
{
  "message": "string (Required, minimum length: 1 character)",
  "session_id": "string (Optional, defaults to 'default')",
  "is_voice": "boolean (Optional, defaults to false)"
}
```

#### Response Body Schema (`ChatResponse`)
```json
{
  "response": "string"
}
```

---

## Part 2: Internal Service & Repository Interfaces

These are the primary public programmatic interfaces used within the JARVIS codebase:

### 1. `KnowledgeGraphService`
* **Purpose**: Coordinates persistent entity graph operations and cache metrics.
* **Execution Flow**: Invokes `EntityRepository` and `RelationshipRepository` within transactional scopes, updating ChromaDB embeddings and invalidating LRU cache keys.
* **Public Methods**:
  * `add_entity(canonical_name: str, entity_type: str, description: str = "") -> Dict[str, Any]`:
    * *Validation*: Enforces normalization of names to trimmed lowercase strings.
  * `add_relationship(source_name: str, source_type: str, target_name: str, target_type: str, relation_type: str, confidence: float = 1.0, weight: float = 1.0) -> Dict[str, Any]`:
    * *Execution Flow*: Resolves/creates source and target entity IDs, checks overlap, and writes to `RelationshipModel`.
  * `delete_entity_safely(entity_id: str) -> bool`:
    * *Execution Flow*: Rewires related edges and deletes entity records, clearing cached lookups.
  * `expand_context(seed_entities: List[str], max_depth: int = 2) -> List[str]`:
    * *Execution Flow*: Traverses edges recursively up to depth limit (max 3), avoiding loops, and returns fact sentences.
  * `query(entity_name: Optional[str] = None, relation_type: Optional[str] = None, depth: int = 1) -> List[Dict[str, Any]]`

### 2. `UserProfileEngine`
* **Purpose**: Maintains session preferences.
* **Public Methods**:
  * `get_profile_context(session_id: str) -> Dict[str, Any]`
  * `update_profile_key(session_id: str, key: str, operation: str, value: str, confidence: float = 1.0) -> Dict[str, Any]`:
    * *Execution Flow*: Modifies values (add/remove lists or set strings) and updates SQLite profiles.

### 3. `TimelineEngine`
* **Purpose**: Renders timeline calendar views.
* **Public Methods**:
  * `generate_timeline(session_id: str, view: str = "upcoming", start_date: Optional[datetime] = None) -> List[Dict[str, Any]]`:
    * *Execution Flow*: Queries `EventRepository` based on date parameters, formats text, and returns event dicts.

### 4. `GraphExporter` & `GraphImporter`
* **Purpose**: Exports and restores graph nodes.
* **Public Methods**:
  * `GraphExporter.export_to_json() -> str`
  * `GraphExporter.export_to_dot() -> str`
  * `GraphExporter.export_to_graphml() -> str`
  * `GraphImporter.import_from_json(json_str: str) -> Dict[str, int]`

---

## Standard Error Codes

### Request Validation Failure (`422 Unprocessable Entity`)
```json
{
  "detail": "Request validation failed",
  "errors": [
    {
      "type": "string_too_short",
      "loc": ["body", "message"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ],
  "error_type": "ValidationError"
}
```

### Bad Gateway (`502 Bad Gateway`)
```json
{
  "detail": "Groq API rate limit exceeded.",
  "error_type": "LLMServiceError"
}
```

### Internal Server Error (`500 Internal Server Error`)
```json
{
  "detail": "An internal server error occurred.",
  "error_type": "InternalServerError"
}
```


