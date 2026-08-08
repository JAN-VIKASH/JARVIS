from typing import List, Dict, Any, Optional
from datetime import datetime

# Valid transitions state machine configuration
VALID_TRANSITIONS = {
    "pending": {"in_progress", "completed", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": {"pending"},
    "cancelled": {"pending"}
}

# Sentinel object to distinguish between "parameter not passed" and "parameter set to None"
_SENTINEL = object()

class TaskService:
    """
    TaskService coordinates business logic around tasks, lifecycle transitions,
    status checks, and updates. Consumes SQLiteMemoryRepository via constructor DI.
    Keeps SQLAlchemy/ORM manipulations strictly inside the repositories.
    """
    def __init__(self, sqlite_repo):
        self.sqlite_repo = sqlite_repo

    async def create_task(
        self,
        session_id: str,
        title: str,
        description: Optional[str] = None,
        status: str = "pending",
        importance: int = 50,
        due_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        if status not in {"pending", "in_progress", "completed", "cancelled"}:
            raise ValueError(f"Invalid initial status: {status}")
        return await self.sqlite_repo.save_task(
            session_id=session_id,
            title=title,
            description=description or "",
            status=status,
            importance=importance,
            due_date=due_date
        )

    async def retrieve_task(self, session_id: str, task_id: int) -> Optional[Dict[str, Any]]:
        return await self.sqlite_repo.get_task_by_id(session_id, task_id)

    async def list_tasks(
        self,
        session_id: str,
        status: Optional[str] = None,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        return await self.sqlite_repo.list_tasks(
            session_id=session_id,
            status=status,
            include_archived=include_archived
        )

    async def search_tasks(self, session_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        return await self.sqlite_repo.search_tasks(session_id, query, limit)

    async def update_task(
        self,
        session_id: str,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        importance: Optional[int] = None,
        due_date: Any = _SENTINEL
    ) -> Dict[str, Any]:
        task = await self.sqlite_repo.get_task_by_id(session_id, task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found in session {session_id}")

        up_title = title if title is not None else task["title"]
        up_description = description if description is not None else task["description"]
        up_importance = importance if importance is not None else task["importance"]
        up_due_date = task["due_date"] if due_date is _SENTINEL else due_date

        return await self.sqlite_repo.save_task(
            session_id=session_id,
            title=up_title,
            description=up_description,
            status=task["status"],
            importance=up_importance,
            due_date=up_due_date,
            task_id=task_id
        )

    async def update_status(self, session_id: str, task_id: int, new_status: str) -> Dict[str, Any]:
        if new_status not in {"pending", "in_progress", "completed", "cancelled"}:
            raise ValueError(f"Invalid status: {new_status}")

        task = await self.sqlite_repo.get_task_by_id(session_id, task_id)
        if not task:
            raise ValueError(f"Task with id {task_id} not found in session {session_id}")

        old_status = task["status"]
        if old_status == new_status:
            return task

        valid = VALID_TRANSITIONS.get(old_status, set())
        if new_status not in valid:
            raise ValueError(f"Invalid lifecycle status transition from '{old_status}' to '{new_status}'")

        return await self.sqlite_repo.save_task(
            session_id=session_id,
            title=task["title"],
            description=task["description"],
            status=new_status,
            importance=task["importance"],
            due_date=task["due_date"],
            task_id=task_id
        )

    async def complete_task(self, session_id: str, task_id: int) -> Dict[str, Any]:
        return await self.update_status(session_id, task_id, "completed")

    async def cancel_task(self, session_id: str, task_id: int) -> Dict[str, Any]:
        return await self.update_status(session_id, task_id, "cancelled")

    async def reopen_task(self, session_id: str, task_id: int) -> Dict[str, Any]:
        return await self.update_status(session_id, task_id, "pending")

    async def archive_task(self, session_id: str, task_id: int) -> bool:
        return await self.sqlite_repo.archive_task(session_id, task_id)

    async def soft_delete_task(self, session_id: str, task_id: int) -> bool:
        return await self.sqlite_repo.soft_delete_task(session_id, task_id)
