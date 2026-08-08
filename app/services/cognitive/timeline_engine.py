from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, exists
from sqlalchemy.orm import aliased
from app.database.session import get_async_session
from app.database.models import EventMemoryModel
from app.database.repositories.event_repository import EventRepository

class TimelineEngine:
    """
    TimelineEngine builds chronological views of a session's events
    (daily, weekly, monthly, upcoming, overdue, completed, cancelled, project).
    Supports sorting by start time, event type, or importance.
    """
    def __init__(self, event_repository: Optional[EventRepository] = None):
        self.event_repository = event_repository or EventRepository()

    async def generate_timeline(
        self,
        session_id: str,
        view: str = "daily",
        start_date: Optional[datetime] = None,
        sort_by: str = "start_time"
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active events filtered by the selected view mode.
        """
        ref_time = start_date or datetime.utcnow()
        events = []
        
        # Determine view target query
        if view == "daily":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 23, 59, 59)
            events = await self.event_repository.find_events_by_range(session_id, start_dt, end_dt)
        elif view == "weekly":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = start_dt + timedelta(days=7, hours=23, minutes=59, seconds=59)
            events = await self.event_repository.find_events_by_range(session_id, start_dt, end_dt)
        elif view == "monthly":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = start_dt + timedelta(days=30, hours=23, minutes=59, seconds=59)
            events = await self.event_repository.find_events_by_range(session_id, start_dt, end_dt)
        elif view == "upcoming":
            events = await self.event_repository.get_upcoming_events(session_id)
        elif view == "overdue":
            events = await self.event_repository.get_overdue_events(session_id)
        elif view == "completed":
            async with get_async_session() as session:
                child_alias = aliased(EventMemoryModel)
                stmt = select(EventMemoryModel).where(
                    and_(
                        EventMemoryModel.session_id == session_id,
                        EventMemoryModel.status == "completed",
                        ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                    )
                ).order_by(EventMemoryModel.start_time.asc())
                result = await session.execute(stmt)
                models = result.scalars().all()
                events = [self.event_repository._to_dict(m) for m in models]
        elif view == "cancelled":
            async with get_async_session() as session:
                child_alias = aliased(EventMemoryModel)
                stmt = select(EventMemoryModel).where(
                    and_(
                        EventMemoryModel.session_id == session_id,
                        EventMemoryModel.status == "cancelled",
                        ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                    )
                ).order_by(EventMemoryModel.start_time.asc())
                result = await session.execute(stmt)
                models = result.scalars().all()
                events = [self.event_repository._to_dict(m) for m in models]
        elif view == "project":
            async with get_async_session() as session:
                child_alias = aliased(EventMemoryModel)
                stmt = select(EventMemoryModel).where(
                    and_(
                        EventMemoryModel.session_id == session_id,
                        EventMemoryModel.event_type.in_(["milestone", "task", "deadline"]),
                        ~exists().where(child_alias.parent_event_id == EventMemoryModel.id)
                    )
                ).order_by(EventMemoryModel.start_time.asc())
                result = await session.execute(stmt)
                models = result.scalars().all()
                events = [self.event_repository._to_dict(m) for m in models]
        else:
            # Global view
            start_dt = datetime(1970, 1, 1, 0, 0, 0)
            end_dt = datetime(2100, 1, 1, 0, 0, 0)
            events = await self.event_repository.find_events_by_range(session_id, start_dt, end_dt)
            
        # Apply sorting logic
        importance_map = {"high": 3, "medium": 2, "low": 1}
        if sort_by == "importance":
            events.sort(key=lambda x: importance_map.get(x.get("importance", "medium"), 2), reverse=True)
        elif sort_by == "event_type":
            events.sort(key=lambda x: str(x.get("event_type", "")))
        else:
            events.sort(key=lambda x: x.get("start_time"))
            
        return events
