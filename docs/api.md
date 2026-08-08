# JARVIS API & Service Interfaces Reference Manual - Phase 5.3 Freeze

This document describes the external HTTP API endpoints and the internal service interfaces implemented up to Phase 5.3.

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
  * `async add_entity(name: str, entity_type: str, description: Optional[str] = None, confidence: float = 1.0, metadata_json: Optional[str] = None) -> Dict[str, Any]`:
    * *Validation*: Enforces normalization of names to trimmed lowercase strings.
  * `async add_relationship(source_name: str, source_type: str, target_name: str, target_type: str, relation_type: str, confidence: float = 1.0, weight: float = 1.0, bidirectional: bool = False, evidence_memory_id: Optional[str] = None, source_session_id: Optional[str] = None) -> Dict[str, Any]`:
    * *Execution Flow*: Resolves/creates source and target entity IDs, checks overlap, and writes to `RelationshipModel`.
  * `async delete_entity_safely(entity_id: str) -> bool`:
    * *Execution Flow*: Rewires related edges and deletes entity records, clearing cached lookups.
  * `async expand_context(entities_list: List[str], max_depth: int = 2) -> List[str]`:
    * *Execution Flow*: Traverses edges recursively up to depth limit (max 3), avoiding loops, and returns fact sentences.
  * `async query(entity: str, relation: Optional[str] = None, depth: int = 1) -> List[Dict[str, Any]]`

### 2. `UserProfileEngine`
* **Purpose**: Maintains session preferences.
* **Public Methods**:
  * `async get_profile_context(session_id: str) -> Dict[str, Any]`
  * `async update_profile_key(session_id: str, key: str, operation: str, value: Any, confidence: float = 1.0, source: str = "llm", source_memory_id: Optional[str] = None) -> Dict[str, Any]`:
    * *Execution Flow*: Modifies values (add/remove lists or set strings) and updates SQLite profiles.

### 3. `TimelineEngine`
* **Purpose**: Renders timeline calendar views and expands recurring events dynamically.
* **Public Methods**:
  * `async generate_timeline(session_id: str, view: str = "daily", start_date: Optional[datetime] = None, sort_by: str = "start_time") -> List[Dict[str, Any]]`:
    * *Execution Flow*: Queries `EventRepository` based on date parameters, calls `RecurringScheduleEngine` to compute recurring occurrences, formats text, and returns sorted event dicts.

### 4. `TaskService`
* **Purpose**: Coordinates task tracking workflows and enforces status transition rules.
* **Public Methods**:
  * `async create_task(session_id: str, title: str, description: Optional[str] = None, status: str = "pending", importance: int = 50, due_date: Optional[datetime] = None) -> Dict[str, Any]`
  * `async retrieve_task(session_id: str, task_id: int) -> Optional[Dict[str, Any]]`
  * `async list_tasks(session_id: str, status: Optional[str] = None, include_archived: bool = False) -> List[Dict[str, Any]]`
  * `async search_tasks(session_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]`
  * `async update_task(session_id: str, task_id: int, title: Optional[str] = None, description: Optional[str] = None, importance: Optional[int] = None, due_date: Any = _SENTINEL) -> Dict[str, Any]`
  * `async update_status(session_id: str, task_id: int, new_status: str) -> Dict[str, Any]`
  * `async complete_task(session_id: str, task_id: int) -> Dict[str, Any]`
  * `async cancel_task(session_id: str, task_id: int) -> Dict[str, Any]`
  * `async reopen_task(session_id: str, task_id: int) -> Dict[str, Any]`
  * `async archive_task(session_id: str, task_id: int) -> bool`
  * `async soft_delete_task(session_id: str, task_id: int) -> bool`

### 5. `RecurringScheduleEngine`
* **Purpose**: Performs timezone-aware date/time computations for recurring event patterns.
* **Public Methods**:
  * `validate_rule(rule: str) -> bool`
  * `calculate_occurrences(start_time: datetime, rule: str, until: Optional[datetime] = None, timezone_str: Optional[str] = None, count: int = 100) -> List[datetime]`
  * `get_next_occurrence(start_time: datetime, rule: str, reference_time: datetime, timezone_str: Optional[str] = None, until: Optional[datetime] = None) -> Optional[datetime]`

### 6. `GraphExporter` & `GraphImporter`
* **Purpose**: Exports and restores graph nodes.
* **Public Methods**:
  * `async GraphExporter.export_to_json() -> str`
  * `async GraphExporter.export_to_dot() -> str`
  * `async GraphExporter.export_to_graphml() -> str`
  * `async GraphImporter.import_from_json(json_data: str) -> Dict[str, int]`

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
