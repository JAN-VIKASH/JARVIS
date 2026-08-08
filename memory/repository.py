"""
Abstract base class definition for Memory repositories.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class BaseMemoryRepository(ABC):
    """
    Abstract interface for saving and querying long-term memories.
    Provides complete storage separation, making it PostgreSQL migration-ready.
    """
    
    @abstractmethod
    async def save_conversation(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """Saves a conversation message segment."""
        pass
        
    @abstractmethod
    async def get_recent_conversations(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent conversation exchanges for a session."""
        pass

    @abstractmethod
    async def save_fact(self, category: str, key: str, value: str, confidence: float, importance: int) -> Dict[str, Any]:
        """Saves or updates a user fact."""
        pass

    @abstractmethod
    async def delete_fact(self, key: str) -> bool:
        """Deletes a user fact."""
        pass

    @abstractmethod
    async def search_facts(self, query: str, limit: int = 10, include_inactive: Optional[bool] = None, include_archived: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Retrieves structured user facts."""
        pass

    @abstractmethod
    async def save_preference(self, category: str, key: str, value: str, confidence: float, importance: int) -> Dict[str, Any]:
        """Saves or updates a user preference."""
        pass

    @abstractmethod
    async def search_preferences(self, query: str, limit: int = 10, include_inactive: Optional[bool] = None, include_archived: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Searches user preferences."""
        pass

    @abstractmethod
    async def save_note(self, title: str, content: str, importance: int) -> Dict[str, Any]:
        """Saves or updates a personal note."""
        pass

    @abstractmethod
    async def search_notes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches notes."""
        pass

    @abstractmethod
    async def save_goal(self, title: str, description: str, status: str, importance: int) -> Dict[str, Any]:
        """Saves or updates a goal."""
        pass

    @abstractmethod
    async def search_goals(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches goals."""
        pass

    @abstractmethod
    async def save_task(
        self,
        session_id: str,
        title: str,
        description: str,
        status: str,
        importance: int,
        due_date: Optional[datetime] = None,
        task_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Saves or updates a task for a session."""
        pass

    @abstractmethod
    async def search_tasks(self, session_id: Optional[str], query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches tasks within a session."""
        pass

    @abstractmethod
    async def get_task_by_id(self, session_id: str, task_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a task by its ID."""
        pass

    @abstractmethod
    async def list_tasks(
        self,
        session_id: str,
        status: Optional[str] = None,
        include_archived: bool = False,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """Lists tasks filtered by status and archive state."""
        pass

    @abstractmethod
    async def archive_task(self, session_id: str, task_id: int) -> bool:
        """Archives a task by setting is_archived to True."""
        pass

    @abstractmethod
    async def soft_delete_task(self, session_id: str, task_id: int) -> bool:
        """Soft deletes a task."""
        pass

    @abstractmethod
    async def clear_session(self, session_id: str) -> bool:
        """Clears all logs for a session."""
        pass

    # Advanced Phase 4.1 interfaces
    @abstractmethod
    async def get_active_fact(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves currently active fact for a key."""
        pass

    @abstractmethod
    async def get_active_preference(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves currently active preference for a key."""
        pass

    @abstractmethod
    async def deactivate_record(self, table_name: str, record_id: int, expected_version: int) -> bool:
        """Optimistic locking deactivation of a record."""
        pass

    @abstractmethod
    async def soft_delete_record(self, table_name: str, record_id: int) -> bool:
        """Soft deletes a record."""
        pass

    @abstractmethod
    async def update_access_metrics(self, table_name: str, record_id: int) -> None:
        """Updates last_accessed_at and increments access_count."""
        pass

    @abstractmethod
    async def save_metadata(
        self,
        memory_type: str,
        record_id: int,
        chroma_id: str,
        importance: int,
        embedding_model: str,
        pending_index: bool
    ) -> Dict[str, Any]:
        """Saves memory metadata."""
        pass

    @abstractmethod
    async def get_pending_indexes(self) -> List[Dict[str, Any]]:
        """Retrieves metadata records flagged for reindexing."""
        pass

    @abstractmethod
    async def update_metadata_status(
        self,
        metadata_id: int,
        status: str,
        pending_index: bool,
        retry_count: int,
        last_retry_at: Any
    ) -> None:
        """Updates background retry metadata status."""
        pass

    @abstractmethod
    async def get_record_by_id_and_type(self, m_type: str, record_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a relational record's full state by type and ID."""
        pass

    @abstractmethod
    async def record_accesses(self, type_id_pairs: List[tuple]) -> None:
        """Executes minimal, isolated updates on access metrics (access_count, last_accessed_at)."""
        pass

    @abstractmethod
    async def update_importance(self, m_type: str, record_id: int, new_importance: int) -> bool:
        """Updates the importance score of a specific memory record."""
        pass

    @abstractmethod
    async def set_memory_active_status(self, m_type: str, record_id: int, is_active: bool) -> bool:
        """Toggles the active status of a memory record."""
        pass

    @abstractmethod
    async def set_memory_archived_status(self, m_type: str, record_id: int, is_archived: bool) -> bool:
        """Toggles the archived status of a memory record."""
        pass

    @abstractmethod
    async def delete_memory_permanently(self, m_type: str, record_id: int) -> bool:
        """Permanently deletes a memory record by removing it from the database."""
        pass

    @abstractmethod
    async def get_conversation_count(self, session_id: str) -> int:
        """Returns the total number of dialogue records in a session."""
        pass

    @abstractmethod
    async def get_oldest_conversations(self, session_id: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieves the oldest dialogue records in a session."""
        pass

    @abstractmethod
    async def delete_conversations_by_ids(self, ids: List[int]) -> bool:
        """Deletes dialogue records by their IDs."""
        pass


