import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.database.repositories.event_repository import EventRepository

logger = logging.getLogger("jarvis.cognitive")

class DuplicateEventResolver:
    """
    Checks for semantic/metadata duplicate overlap of events to prevent duplicate records.
    """
    def __init__(self, event_repository: Optional[EventRepository] = None):
        self.event_repository = event_repository or EventRepository()

    async def resolve_duplicate(
        self,
        session_id: str,
        title: str,
        start_time: datetime,
        event_type: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Queries the database for existing events that match the title, start_time (within 30m), and event_type.
        Returns the existing duplicate event if found.
        """
        clean_title = title.lower().strip()
        
        try:
            # Look for active events in a 30-minute window around the target start_time
            delta = timedelta(minutes=30)
            events = await self.event_repository.find_events_by_range(
                session_id=session_id,
                start_time=start_time - delta,
                end_time=start_time + delta,
                include_all_versions=False
            )
            
            for ev in events:
                ev_title = ev["title"].lower().strip()
                # 1. Exact title match
                if ev_title == clean_title:
                    return ev
                    
                # 2. Simple lexical intersection check
                words1 = set(w for w in clean_title.split() if len(w) > 2)
                words2 = set(w for w in ev_title.split() if len(w) > 2)
                if words1 and words2 and len(words1.intersection(words2)) / max(len(words1), len(words2)) >= 0.7:
                    logger.info(f"DuplicateEventResolver matched event '{ev['title']}' lexically with '{title}'")
                    return ev
        except Exception as e:
            logger.error(f"Failed to resolve duplicate in DuplicateEventResolver: {e}")
            
        return None
