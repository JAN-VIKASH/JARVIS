import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, delete, and_, exists
from sqlalchemy.orm import aliased
from app.database.session import get_async_session
from app.database.models import EventMemoryModel

logger = logging.getLogger("jarvis.database")

class EventRepository:
    """
    Handles SQLite/PostgreSQL interactions with the event_memories table.
    Enforces Repository Pattern and Event Versioning.
    """
    async def save_event(
        self,
        session_id: str,
        title: str,
        description: Optional[str],
        event_type: Optional[str],
        start_time: datetime,
        end_time: Optional[datetime],
        is_all_day: bool = False,
        raw_text: Optional[str] = None,
        status: str = "planned",
        importance: str = "medium",
        confidence: Optional[float] = None,
        embedding_id: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            model = EventMemoryModel(
                id=str(uuid.uuid4()),
                session_id=session_id,
                title=title,
                description=description,
                event_type=event_type,
                start_time=start_time,
                end_time=end_time,
                is_all_day=is_all_day,
                raw_text=raw_text,
                status=status,
                importance=importance,
                confidence=confidence,
                version=1,
                parent_event_id=None,
                embedding_id=embedding_id
            )
            session.add(model)
            await session.commit()
            return self._to_dict(model)

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(EventMemoryModel).where(EventMemoryModel.id == event_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def update_event(
        self,
        event_id: str,
        title: str,
        description: Optional[str],
        event_type: Optional[str],
        start_time: datetime,
        end_time: Optional[datetime],
        is_all_day: bool,
        status: str,
        importance: str,
        confidence: float,
        embedding_id: Optional[str] = None,
        raw_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a new version of the event to preserve history (copy-on-write versioning).
        """
        async with get_async_session() as session:
            # 1. Fetch old event to reference parent
            stmt = select(EventMemoryModel).where(EventMemoryModel.id == event_id)
            result = await session.execute(stmt)
            old_model = result.scalar_one_or_none()
            if not old_model:
                raise ValueError(f"Event with id {event_id} not found")
                
            # 2. Insert new versioned event
            new_model = EventMemoryModel(
                id=str(uuid.uuid4()),
                session_id=old_model.session_id,
                title=title,
                description=description,
                event_type=event_type,
                start_time=start_time,
                end_time=end_time,
                is_all_day=is_all_day,
                status=status,
                importance=importance,
                confidence=confidence,
                version=old_model.version + 1,
                parent_event_id=old_model.id,
                embedding_id=embedding_id or old_model.embedding_id,
                raw_text=raw_text or old_model.raw_text
            )
            session.add(new_model)
            await session.commit()
            return self._to_dict(new_model)

    async def update_event_status(self, event_id: str, status: str) -> Dict[str, Any]:
        """
        Versioned update to set event status (planned, completed, cancelled, postponed).
        """
        async with get_async_session() as session:
            stmt = select(EventMemoryModel).where(EventMemoryModel.id == event_id)
            result = await session.execute(stmt)
            old_model = result.scalar_one_or_none()
            if not old_model:
                raise ValueError(f"Event with id {event_id} not found")
                
            new_model = EventMemoryModel(
                id=str(uuid.uuid4()),
                session_id=old_model.session_id,
                title=old_model.title,
                description=old_model.description,
                event_type=old_model.event_type,
                start_time=old_model.start_time,
                end_time=old_model.end_time,
                is_all_day=old_model.is_all_day,
                status=status,
                importance=old_model.importance,
                confidence=old_model.confidence,
                version=old_model.version + 1,
                parent_event_id=old_model.id,
                embedding_id=old_model.embedding_id,
                raw_text=old_model.raw_text
            )
            session.add(new_model)
            await session.commit()
            return self._to_dict(new_model)

    async def archive_event(self, event_id: str) -> bool:
        """
        Cancels/archives the target event.
        """
        try:
            await self.update_event_status(event_id, "cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to archive event {event_id}: {e}")
            return False

    async def find_events_by_range(
        self,
        session_id: str,
        start_time: datetime,
        end_time: datetime,
        include_all_versions: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Queries active events (latest version only) within a target datetime range.
        """
        async with get_async_session() as session:
            filters = [
                EventMemoryModel.session_id == session_id,
                EventMemoryModel.start_time >= start_time,
                EventMemoryModel.start_time <= end_time
            ]
            if not include_all_versions:
                child_alias = aliased(EventMemoryModel)
                filters.append(~exists().where(child_alias.parent_event_id == EventMemoryModel.id))
                
            stmt = select(EventMemoryModel).where(and_(*filters)).order_by(EventMemoryModel.start_time.asc())
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_dict(m) for m in models]

    async def get_today_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Returns active events starting today in UTC.
        """
        ref = datetime.utcnow()
        start_dt = datetime(ref.year, ref.month, ref.day, 0, 0, 0)
        end_dt = datetime(ref.year, ref.month, ref.day, 23, 59, 59)
        return await self.find_events_by_range(session_id, start_dt, end_dt)

    async def get_upcoming_events(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns upcoming active events starting in the future.
        """
        async with get_async_session() as session:
            ref = datetime.utcnow()
            child_alias = aliased(EventMemoryModel)
            stmt = select(EventMemoryModel).where(
                and_(
                    EventMemoryModel.session_id == session_id,
                    EventMemoryModel.start_time >= ref,
                    EventMemoryModel.status == "planned",
                    ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                )
            ).order_by(EventMemoryModel.start_time.asc()).limit(limit)
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_dict(m) for m in models]

    async def get_overdue_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Returns overdue active events starting in the past that are not completed/cancelled.
        """
        async with get_async_session() as session:
            ref = datetime.utcnow()
            child_alias = aliased(EventMemoryModel)
            stmt = select(EventMemoryModel).where(
                and_(
                    EventMemoryModel.session_id == session_id,
                    EventMemoryModel.start_time < ref,
                    EventMemoryModel.status == "planned",
                    ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                )
            ).order_by(EventMemoryModel.start_time.asc())
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_dict(m) for m in models]

    async def find_duplicate_event(
        self,
        session_id: str,
        title: str,
        start_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Checks for duplicate events in the same session with similar timestamps.
        """
        async with get_async_session() as session:
            delta = timedelta(minutes=30)
            child_alias = aliased(EventMemoryModel)
            stmt = select(EventMemoryModel).where(
                and_(
                    EventMemoryModel.session_id == session_id,
                    EventMemoryModel.title == title,
                    EventMemoryModel.start_time >= start_time - delta,
                    EventMemoryModel.start_time <= start_time + delta,
                    ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def get_event_versions(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Walks the parent link chain from target event backwards to retrieve revision history.
        """
        async with get_async_session() as session:
            versions = []
            curr_id = event_id
            while curr_id:
                stmt = select(EventMemoryModel).where(EventMemoryModel.id == curr_id)
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()
                if not model:
                    break
                versions.append(self._to_dict(model))
                curr_id = model.parent_event_id
            return versions

    async def update_embedding_id(self, event_id: str, embedding_id: str) -> None:
        """
        Directly sets the embedding_id for a specific event version.
        """
        async with get_async_session() as session:
            stmt = select(EventMemoryModel).where(EventMemoryModel.id == event_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if model:
                model.embedding_id = embedding_id
                await session.commit()

    def _to_dict(self, model: EventMemoryModel) -> Dict[str, Any]:
        return {
            "id": model.id,
            "session_id": model.session_id,
            "title": model.title,
            "description": model.description,
            "event_type": model.event_type,
            "start_time": model.start_time,
            "end_time": model.end_time,
            "is_all_day": model.is_all_day,
            "raw_text": model.raw_text,
            "status": model.status,
            "importance": model.importance,
            "confidence": model.confidence,
            "version": model.version,
            "parent_event_id": model.parent_event_id,
            "embedding_id": model.embedding_id,
            "created_at": model.created_at,
            "updated_at": model.updated_at
        }
