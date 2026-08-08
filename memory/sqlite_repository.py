"""
SQLite implementation of the BaseMemoryRepository using SQLAlchemy async sessions.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, delete
from app.database.session import get_async_session
from app.database.models import (
    ConversationModel,
    UserFactModel,
    PreferenceModel,
    NoteModel,
    GoalModel,
    TaskModel,
    MemoryMetadataModel
)
from memory.repository import BaseMemoryRepository

class SQLiteMemoryRepository(BaseMemoryRepository):
    """
    SQLite-backed persistent repository implementation.
    Acts as a repository wrapper around the async SQLAlchemy session context.
    """
    
    def _get_model_class(self, table_name: str):
        mapping = {
            "user_facts": UserFactModel,
            "preferences": PreferenceModel,
            "goals": GoalModel,
            "tasks": TaskModel,
            "notes": NoteModel,
            "memory_metadata": MemoryMetadataModel
        }
        return mapping.get(table_name)
        
    async def save_conversation(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        async with get_async_session() as session:
            model = ConversationModel(
                session_id=session_id,
                role=role,
                content=content
            )
            session.add(model)
            await session.flush()
            return {
                "id": model.id,
                "session_id": model.session_id,
                "role": model.role,
                "content": model.content,
                "timestamp": model.timestamp
            }

    async def get_recent_conversations(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(ConversationModel).where(
                ConversationModel.session_id == session_id
            ).order_by(ConversationModel.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp
                }
                for m in reversed(models)
            ]

    async def save_fact(self, category: str, key: str, value: str, confidence: float, importance: int) -> Dict[str, Any]:
        async with get_async_session() as session:
            # Check for active identical key/value fact
            stmt = select(UserFactModel).where(
                UserFactModel.category == category,
                UserFactModel.key == key,
                UserFactModel.value == value,
                UserFactModel.is_deleted == False
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.is_active = True
                model.is_archived = False
                model.confidence = confidence
                model.importance = importance
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
                model.updated_at = datetime.utcnow()
            else:
                # Deactivate other active version
                deact_stmt = select(UserFactModel).where(
                    UserFactModel.key == key,
                    UserFactModel.is_active == True,
                    UserFactModel.is_deleted == False
                )
                deact_res = await session.execute(deact_stmt)
                active_records = deact_res.scalars().all()
                version = 1
                for old in active_records:
                    old.is_active = False
                    old.updated_at = datetime.utcnow()
                    version = max(version, old.version + 1)
                    
                model = UserFactModel(
                    category=category,
                    key=key,
                    value=value,
                    confidence=confidence,
                    importance=importance,
                    version=version,
                    is_active=True
                )
                session.add(model)
                
            await session.flush()
            return {
                "id": model.id,
                "category": model.category,
                "key": model.key,
                "value": model.value,
                "confidence": model.confidence,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def delete_fact(self, key: str) -> bool:
        async with get_async_session() as session:
            stmt = select(UserFactModel).where(
                UserFactModel.key == key,
                UserFactModel.is_deleted == False
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
            if not records:
                return False
            for r in records:
                r.is_deleted = True
                r.deleted_at = datetime.utcnow()
                r.is_active = False
            return True

    async def search_facts(
        self,
        query: str,
        limit: int = 10,
        include_inactive: Optional[bool] = None,
        include_archived: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            query_lower = query.lower()
            if include_inactive is None:
                include_inactive = any(w in query_lower for w in ["history", "previous", "previously", "version", "before", "earlier", "formerly", "past"])
            if include_archived is None:
                include_archived = any(w in query_lower for w in ["archive", "archived", "past", "historical"])
            
            stmt = select(UserFactModel).where(UserFactModel.is_deleted == False)
            if not include_inactive:
                stmt = stmt.where(UserFactModel.is_active == True)
            if not include_archived:
                stmt = stmt.where(UserFactModel.is_archived == False)
                
            stmt = stmt.where(
                (UserFactModel.key.like(f"%{query}%")) |
                (UserFactModel.category.like(f"%{query}%")) |
                (UserFactModel.value.like(f"%{query}%"))
            ).order_by(UserFactModel.importance.desc()).limit(limit)
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "category": m.category,
                    "key": m.key,
                    "value": m.value,
                    "confidence": m.confidence,
                    "importance": m.importance,
                    "version": m.version,
                    "is_active": m.is_active,
                    "is_archived": m.is_archived,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "updated_at": m.updated_at
                }
                for m in models
            ]

    async def save_preference(self, category: str, key: str, value: str, confidence: float, importance: int) -> Dict[str, Any]:
        async with get_async_session() as session:
            # Check for active identical key/value preference
            stmt = select(PreferenceModel).where(
                PreferenceModel.category == category,
                PreferenceModel.key == key,
                PreferenceModel.value == value,
                PreferenceModel.is_deleted == False
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.is_active = True
                model.is_archived = False
                model.confidence = confidence
                model.importance = importance
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
                model.updated_at = datetime.utcnow()
            else:
                # Deactivate other active version
                deact_stmt = select(PreferenceModel).where(
                    PreferenceModel.key == key,
                    PreferenceModel.is_active == True,
                    PreferenceModel.is_deleted == False
                )
                deact_res = await session.execute(deact_stmt)
                active_records = deact_res.scalars().all()
                version = 1
                for old in active_records:
                    old.is_active = False
                    old.updated_at = datetime.utcnow()
                    version = max(version, old.version + 1)
                    
                model = PreferenceModel(
                    category=category,
                    key=key,
                    value=value,
                    confidence=confidence,
                    importance=importance,
                    version=version,
                    is_active=True
                )
                session.add(model)
                
            await session.flush()
            return {
                "id": model.id,
                "category": model.category,
                "key": model.key,
                "value": model.value,
                "confidence": model.confidence,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def search_preferences(
        self,
        query: str,
        limit: int = 10,
        include_inactive: Optional[bool] = None,
        include_archived: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            query_lower = query.lower()
            if include_inactive is None:
                include_inactive = any(w in query_lower for w in ["history", "previous", "previously", "version", "before", "earlier", "formerly", "past"])
            if include_archived is None:
                include_archived = any(w in query_lower for w in ["archive", "archived", "past", "historical"])
            
            stmt = select(PreferenceModel).where(PreferenceModel.is_deleted == False)
            if not include_inactive:
                stmt = stmt.where(PreferenceModel.is_active == True)
            if not include_archived:
                stmt = stmt.where(PreferenceModel.is_archived == False)
                
            stmt = stmt.where(
                (PreferenceModel.key.like(f"%{query}%")) |
                (PreferenceModel.category.like(f"%{query}%")) |
                (PreferenceModel.value.like(f"%{query}%"))
            ).order_by(PreferenceModel.importance.desc()).limit(limit)
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "category": m.category,
                    "key": m.key,
                    "value": m.value,
                    "confidence": m.confidence,
                    "importance": m.importance,
                    "version": m.version,
                    "is_active": m.is_active,
                    "is_archived": m.is_archived,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "updated_at": m.updated_at
                }
                for m in models
            ]

    async def save_note(self, title: str, content: str, importance: int) -> Dict[str, Any]:
        async with get_async_session() as session:
            stmt = select(NoteModel).where(
                NoteModel.title == title,
                NoteModel.is_deleted == False
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.content = content
                model.importance = importance
                model.updated_at = datetime.utcnow()
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
            else:
                model = NoteModel(
                    title=title,
                    content=content,
                    importance=importance,
                    is_active=True
                )
                session.add(model)
                
            await session.flush()
            return {
                "id": model.id,
                "title": model.title,
                "content": model.content,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def search_notes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            query_lower = query.lower()
            include_inactive = any(w in query_lower for w in ["history", "previous", "version"])
            include_archived = any(w in query_lower for w in ["archive", "past", "historical"])
            
            stmt = select(NoteModel).where(NoteModel.is_deleted == False)
            if not include_inactive:
                stmt = stmt.where(NoteModel.is_active == True)
            if not include_archived:
                stmt = stmt.where(NoteModel.is_archived == False)
                
            stmt = stmt.where(
                (NoteModel.title.like(f"%{query}%")) |
                (NoteModel.content.like(f"%{query}%"))
            ).order_by(NoteModel.importance.desc()).limit(limit)
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "title": m.title,
                    "content": m.content,
                    "importance": m.importance,
                    "version": m.version,
                    "is_active": m.is_active,
                    "is_archived": m.is_archived,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "updated_at": m.updated_at
                }
                for m in models
            ]

    async def save_goal(self, title: str, description: str, status: str, importance: int) -> Dict[str, Any]:
        async with get_async_session() as session:
            stmt = select(GoalModel).where(
                GoalModel.title == title,
                GoalModel.is_deleted == False
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.description = description
                model.status = status
                model.importance = importance
                model.updated_at = datetime.utcnow()
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
            else:
                model = GoalModel(
                    title=title,
                    description=description,
                    status=status,
                    importance=importance,
                    is_active=True
                )
                session.add(model)
                
            await session.flush()
            return {
                "id": model.id,
                "title": model.title,
                "description": model.description,
                "status": model.status,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def search_goals(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            query_lower = query.lower()
            include_inactive = any(w in query_lower for w in ["history", "previous", "version"])
            include_archived = any(w in query_lower for w in ["archive", "past", "historical"])
            
            stmt = select(GoalModel).where(GoalModel.is_deleted == False)
            if not include_inactive:
                stmt = stmt.where(GoalModel.is_active == True)
            if not include_archived:
                stmt = stmt.where(GoalModel.is_archived == False)
                
            stmt = stmt.where(
                (GoalModel.title.like(f"%{query}%")) |
                (GoalModel.description.like(f"%{query}%"))
            ).order_by(GoalModel.importance.desc()).limit(limit)
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "title": m.title,
                    "description": m.description,
                    "status": m.status,
                    "importance": m.importance,
                    "version": m.version,
                    "is_active": m.is_active,
                    "is_archived": m.is_archived,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "updated_at": m.updated_at
                }
                for m in models
            ]

    async def save_task(self, title: str, description: str, status: str, importance: int) -> Dict[str, Any]:
        async with get_async_session() as session:
            stmt = select(TaskModel).where(
                TaskModel.title == title,
                TaskModel.is_deleted == False
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.description = description
                model.status = status
                model.importance = importance
                model.updated_at = datetime.utcnow()
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
            else:
                model = TaskModel(
                    title=title,
                    description=description,
                    status=status,
                    importance=importance,
                    is_active=True
                )
                session.add(model)
                
            await session.flush()
            return {
                "id": model.id,
                "title": model.title,
                "description": model.description,
                "status": model.status,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def search_tasks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            query_lower = query.lower()
            include_inactive = any(w in query_lower for w in ["history", "previous", "version"])
            include_archived = any(w in query_lower for w in ["archive", "past", "historical"])
            
            stmt = select(TaskModel).where(TaskModel.is_deleted == False)
            if not include_inactive:
                stmt = stmt.where(TaskModel.is_active == True)
            if not include_archived:
                stmt = stmt.where(TaskModel.is_archived == False)
                
            stmt = stmt.where(
                (TaskModel.title.like(f"%{query}%")) |
                (TaskModel.description.like(f"%{query}%"))
            ).order_by(TaskModel.importance.desc()).limit(limit)
            
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "title": m.title,
                    "description": m.description,
                    "status": m.status,
                    "importance": m.importance,
                    "version": m.version,
                    "is_active": m.is_active,
                    "is_archived": m.is_archived,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "updated_at": m.updated_at
                }
                for m in models
            ]

    async def clear_session(self, session_id: str) -> bool:
        async with get_async_session() as session:
            stmt = delete(ConversationModel).where(ConversationModel.session_id == session_id)
            result = await session.execute(stmt)
            return (result.rowcount or 0) > 0

    # Advanced Phase 4.1 implementations
    async def get_active_fact(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(UserFactModel).where(
                UserFactModel.category == category,
                UserFactModel.key == key,
                UserFactModel.is_active == True,
                UserFactModel.is_deleted == False
            )
            result = await session.execute(stmt)
            m = result.scalars().first()
            if not m:
                return None
            return {
                "id": m.id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "importance": m.importance,
                "version": m.version,
                "is_active": m.is_active,
                "is_archived": m.is_archived,
                "access_count": m.access_count,
                "last_accessed_at": m.last_accessed_at
            }

    async def get_active_preference(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(PreferenceModel).where(
                PreferenceModel.category == category,
                PreferenceModel.key == key,
                PreferenceModel.is_active == True,
                PreferenceModel.is_deleted == False
            )
            result = await session.execute(stmt)
            m = result.scalars().first()
            if not m:
                return None
            return {
                "id": m.id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "importance": m.importance,
                "version": m.version,
                "is_active": m.is_active,
                "is_archived": m.is_archived,
                "access_count": m.access_count,
                "last_accessed_at": m.last_accessed_at
            }

    async def deactivate_record(self, table_name: str, record_id: int, expected_version: int) -> bool:
        model_class = self._get_model_class(table_name)
        if not model_class:
            return False
        async with get_async_session() as session:
            stmt = select(model_class).where(
                model_class.id == record_id,
                model_class.version == expected_version,
                model_class.is_active == True
            )
            result = await session.execute(stmt)
            model = result.scalars().first()
            if not model:
                return False
            model.is_active = False
            model.updated_at = datetime.utcnow()
            await session.flush()
            return True

    async def soft_delete_record(self, table_name: str, record_id: int) -> bool:
        model_class = self._get_model_class(table_name)
        if not model_class:
            return False
        async with get_async_session() as session:
            stmt = select(model_class).where(model_class.id == record_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            if not model:
                return False
            model.is_deleted = True
            model.deleted_at = datetime.utcnow()
            model.is_active = False
            await session.flush()
            return True

    async def update_access_metrics(self, table_name: str, record_id: int) -> None:
        model_class = self._get_model_class(table_name)
        if not model_class:
            return
        async with get_async_session() as session:
            stmt = select(model_class).where(model_class.id == record_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            if model:
                model.last_accessed_at = datetime.utcnow()
                model.access_count = (model.access_count or 0) + 1
                if getattr(model, "is_archived", False):
                    model.is_archived = False
                await session.flush()

    async def save_metadata(
        self,
        memory_type: str,
        record_id: int,
        chroma_id: str,
        importance: int,
        embedding_model: str,
        pending_index: bool
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            stmt = select(MemoryMetadataModel).where(MemoryMetadataModel.chroma_id == chroma_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if model:
                model.importance = importance
                model.embedding_model = embedding_model
                model.pending_index = pending_index
                model.last_indexed = datetime.utcnow()
                if not pending_index:
                    model.status = "active"
            else:
                model = MemoryMetadataModel(
                    memory_type=memory_type,
                    record_id=record_id,
                    chroma_id=chroma_id,
                    importance=importance,
                    embedding_model=embedding_model,
                    pending_index=pending_index,
                    status="active" if not pending_index else "pending"
                )
                session.add(model)
            await session.flush()
            return {
                "id": model.id,
                "memory_type": model.memory_type,
                "record_id": model.record_id,
                "chroma_id": model.chroma_id,
                "importance": model.importance,
                "embedding_model": model.embedding_model,
                "pending_index": model.pending_index,
                "retry_count": model.retry_count,
                "status": model.status
            }

    async def get_pending_indexes(self) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(MemoryMetadataModel).where(
                MemoryMetadataModel.pending_index == True,
                MemoryMetadataModel.status != "failed"
            )
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "memory_type": m.memory_type,
                    "record_id": m.record_id,
                    "chroma_id": m.chroma_id,
                    "importance": m.importance,
                    "embedding_model": m.embedding_model,
                    "pending_index": m.pending_index,
                    "retry_count": m.retry_count,
                    "last_retry_at": m.last_retry_at,
                    "status": m.status
                }
                for m in models
            ]

    async def update_metadata_status(
        self,
        metadata_id: int,
        status: str,
        pending_index: bool,
        retry_count: int,
        last_retry_at: Any
    ) -> None:
        async with get_async_session() as session:
            stmt = select(MemoryMetadataModel).where(MemoryMetadataModel.id == metadata_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            if model:
                model.status = status
                model.pending_index = pending_index
                model.retry_count = retry_count
                model.last_retry_at = last_retry_at
                await session.flush()

    async def get_record_by_id_and_type(self, m_type: str, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a relational record's full state (including access count, version, timestamps) by type and ID.
        """
        if m_type == "fact":
            model_class = UserFactModel
        elif m_type == "preference":
            model_class = PreferenceModel
        elif m_type == "goal":
            model_class = GoalModel
        elif m_type == "task":
            model_class = TaskModel
        elif m_type == "note":
            model_class = NoteModel
        elif m_type == "conversation":
            model_class = ConversationModel
        else:
            return None
            
        async with get_async_session() as session:
            stmt = select(model_class).where(model_class.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if not m:
                return None
                
            is_archived = getattr(m, "is_archived", False)
            is_deleted = getattr(m, "is_deleted", False)
            is_active = getattr(m, "is_active", True)
            
            result = {
                "id": m.id,
                "is_archived": is_archived,
                "is_deleted": is_deleted,
                "is_active": is_active,
                "confidence": getattr(m, "confidence", 1.0),
                "importance": getattr(m, "importance", 50),
                "access_count": getattr(m, "access_count", 0),
                "last_accessed_at": getattr(m, "last_accessed_at", None),
                "updated_at": getattr(m, "updated_at", None)
            }
            
            if m_type == "fact" or m_type == "preference":
                result["category"] = m.category
                result["key"] = m.key
                result["value"] = m.value
            elif m_type == "goal" or m_type == "task":
                result["category"] = m_type + "s"
                result["key"] = m.title
                result["value"] = m.description
            elif m_type == "note":
                result["category"] = "notes"
                result["key"] = m.title
                result["value"] = m.content
            return result

