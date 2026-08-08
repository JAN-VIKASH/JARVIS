from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, exists
from sqlalchemy.orm import aliased
from app.database.session import get_async_session
from app.database.models import EventMemoryModel
from app.database.repositories.event_repository import EventRepository
from app.services.cognitive.recurring_schedule_engine import RecurringScheduleEngine
import logging

logger = logging.getLogger("jarvis.cognitive")

class TimelineEngine:
    """
    TimelineEngine builds chronological views of a session's events
    (daily, weekly, monthly, upcoming, overdue, completed, cancelled, project).
    Supports sorting by start time, event type, or importance.
    Expands recurring schedule occurrences on-the-fly.
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
        Retrieves active events and computes recurring occurrences filtered by the selected view mode.
        """
        ref_time = start_date or datetime.utcnow()
        
        # Calculate time windows based on the selected view
        if view == "daily":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 23, 59, 59)
        elif view == "weekly":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = start_dt + timedelta(days=7, hours=23, minutes=59, seconds=59)
        elif view == "monthly":
            start_dt = datetime(ref_time.year, ref_time.month, ref_time.day, 0, 0, 0)
            end_dt = start_dt + timedelta(days=30, hours=23, minutes=59, seconds=59)
        elif view == "upcoming":
            start_dt = ref_time
            end_dt = ref_time + timedelta(days=365)  # 1 year lookahead
        elif view == "overdue":
            start_dt = datetime(1970, 1, 1)
            end_dt = ref_time
        else:  # global / completed / cancelled / project
            start_dt = datetime(1970, 1, 1)
            end_dt = datetime(2100, 1, 1)

        events = []
        # Query all active (latest version only) events for the session
        all_latest = await self.event_repository.get_all_latest_events(session_id)
        
        for ev in all_latest:
            rule = ev.get("recurrence_rule")
            if not rule:
                # 1. Process non-recurring events
                # Filter by status and view rules
                if view == "completed":
                    if ev["status"] == "completed":
                        events.append(ev)
                elif view == "cancelled":
                    if ev["status"] == "cancelled":
                        events.append(ev)
                elif view == "project":
                    if ev["event_type"] in ("milestone", "task", "deadline") and ev["status"] not in ("completed", "cancelled"):
                        events.append(ev)
                elif view == "overdue":
                    if ev["start_time"] < ref_time and ev["status"] == "planned":
                        events.append(ev)
                elif view == "upcoming":
                    if ev["start_time"] >= ref_time and ev["status"] == "planned":
                        events.append(ev)
                else:  # daily / weekly / monthly / global
                    if ev["start_time"] >= start_dt and ev["start_time"] <= end_dt:
                        events.append(ev)
            else:
                # 2. Process recurring events
                # Skip series if series-level status is completed/cancelled for non-status queries
                if view == "completed":
                    if ev["status"] == "completed":
                        events.append(ev)
                    continue
                if view == "cancelled":
                    if ev["status"] == "cancelled":
                        events.append(ev)
                    continue
                if ev["status"] in ("completed", "cancelled"):
                    continue

                try:
                    occs = RecurringScheduleEngine.calculate_occurrences(
                        start_time=ev["start_time"],
                        rule=rule,
                        until=ev.get("recurrence_until"),
                        timezone_str=ev.get("timezone"),
                        count=100
                    )
                    
                    if view == "upcoming":
                        # Find the first occurrence >= ref_time
                        next_occ = RecurringScheduleEngine.get_next_occurrence(
                            start_time=ev["start_time"],
                            rule=rule,
                            reference_time=ref_time,
                            timezone_str=ev.get("timezone"),
                            until=ev.get("recurrence_until")
                        )
                        if next_occ:
                            ev_occ = ev.copy()
                            ev_occ["start_time"] = next_occ
                            if ev.get("end_time") and ev.get("start_time"):
                                ev_occ["end_time"] = next_occ + (ev["end_time"] - ev["start_time"])
                            events.append(ev_occ)
                    elif view == "overdue":
                        # Any occurrence in the past (before ref_time)
                        for occ in occs:
                            if occ < ref_time:
                                ev_occ = ev.copy()
                                ev_occ["start_time"] = occ
                                if ev.get("end_time") and ev.get("start_time"):
                                    ev_occ["end_time"] = occ + (ev["end_time"] - ev["start_time"])
                                events.append(ev_occ)
                    elif view == "project":
                        if ev["event_type"] in ("milestone", "task", "deadline"):
                            events.append(ev)
                    else:  # daily / weekly / monthly / global
                        for occ in occs:
                            if occ >= start_dt and occ <= end_dt:
                                ev_occ = ev.copy()
                                ev_occ["start_time"] = occ
                                if ev.get("end_time") and ev.get("start_time"):
                                    ev_occ["end_time"] = occ + (ev["end_time"] - ev["start_time"])
                                events.append(ev_occ)
                except Exception as e:
                    logger.error(f"Failed to expand recurring occurrences for event {ev['id']}: {e}")

        # Apply sorting logic
        importance_map = {"high": 3, "medium": 2, "low": 1}
        if sort_by == "importance":
            events.sort(key=lambda x: importance_map.get(x.get("importance", "medium"), 2), reverse=True)
        elif sort_by == "event_type":
            events.sort(key=lambda x: str(x.get("event_type", "")))
        else:
            events.sort(key=lambda x: x.get("start_time"))

        return events
