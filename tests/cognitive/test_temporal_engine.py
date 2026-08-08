import asyncio
import json
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.database.migrations import init_db
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.database.repositories.event_repository import EventRepository
from app.database.session import get_async_session
from app.database.models import EventMemoryModel
from app.services.cognitive.time_normalizer import TimeNormalizer
from app.services.cognitive.event_extractor import EventExtractor
from app.services.cognitive.timeline_engine import TimelineEngine
from memory.test_memory import clear_database

class MockLLMForTemporal(BaseLLM):
    """
    Mock LLM provider yielding structured time coordinates and event structures.
    """
    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        msg = request.message.lower()
        
        if "normalize this time phrase" in msg:
            if "next monday" in msg:
                resp = "2026-08-10T09:00:00"
            elif "last month" in msg:
                resp = "2026-07-15T09:00:00"
            elif "tomorrow at 3pm" in msg:
                resp = "2026-08-08T15:00:00"
            elif "tomorrow at 4pm" in msg:
                resp = "2026-08-08T16:00:00"
            else:
                resp = "2026-08-07T09:00:00"
        elif "extract events from" in msg:
            if "meeting with jan" in msg:
                resp = json.dumps([
                    {
                        "title": "Meeting with Jan",
                        "description": "Discuss project status",
                        "event_type": "meeting",
                        "start_time_phrase": "tomorrow at 3pm",
                        "end_time_phrase": "tomorrow at 4pm",
                        "is_all_day": False
                    }
                ])
            else:
                resp = "[]"
        else:
            resp = "[]"
            
        return LLMResult(
            response=resp,
            provider="mock",
            model="mock",
            latency=0.01,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20
        )

class TestTemporalEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        await clear_database()
        async with get_async_session() as session:
            await session.execute(EventMemoryModel.__table__.delete())
            await session.commit()
        self.mock_llm = MockLLMForTemporal()
        self.normalizer = TimeNormalizer(self.mock_llm)
        self.extractor = EventExtractor(self.mock_llm)
        self.event_repo = EventRepository()
        self.timeline_engine = TimelineEngine(self.event_repo)
        
        # Target reference execution time: Friday, 2026-08-07 12:00:00
        self.ref_time = datetime(2026, 8, 7, 12, 0, 0)

    async def test_time_normalizer_rules(self):
        # 1. Today
        t1 = await self.normalizer.normalize("today", self.ref_time)
        self.assertEqual(t1, self.ref_time)
        
        # 2. Yesterday
        t2 = await self.normalizer.normalize("yesterday", self.ref_time)
        self.assertEqual(t2, self.ref_time - timedelta(days=1))
        
        # 3. Tomorrow
        t3 = await self.normalizer.normalize("tomorrow", self.ref_time)
        self.assertEqual(t3, self.ref_time + timedelta(days=1))
        
        # 4. X days ago
        t4 = await self.normalizer.normalize("5 days ago", self.ref_time)
        self.assertEqual(t4, self.ref_time - timedelta(days=5))

        # 5. Complex fallback to LLM
        t5 = await self.normalizer.normalize("next Monday", self.ref_time)
        self.assertEqual(t5, datetime(2026, 8, 10, 9, 0, 0))

    async def test_event_extractor(self):
        events = await self.extractor.extract_events(
            "We have a meeting with Jan tomorrow at 3pm to talk about the project.",
            self.ref_time
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["title"], "Meeting with Jan")
        self.assertEqual(event["event_type"], "meeting")
        # Assert start time is resolved (tomorrow is 2026-08-08)
        self.assertEqual(event["start_time"].date(), datetime(2026, 8, 8).date())

    async def test_event_repository_and_timeline(self):
        session_id = "session_timeline_test"
        
        # Save mock events
        evt1 = await self.event_repo.save_event(
            session_id=session_id,
            title="Daily Standup",
            description="Status updates",
            event_type="meeting",
            start_time=datetime(2026, 8, 7, 10, 0, 0),
            end_time=datetime(2026, 8, 7, 10, 30, 0)
        )
        self.assertIsNotNone(evt1["id"])
        
        evt2 = await self.event_repo.save_event(
            session_id=session_id,
            title="Code Review",
            description="PR check",
            event_type="task",
            start_time=datetime(2026, 8, 7, 15, 0, 0),
            end_time=None
        )
        
        evt3 = await self.event_repo.save_event(
            session_id=session_id,
            title="Milestone Delivery",
            description="Phase 5 release",
            event_type="milestone",
            start_time=datetime(2026, 8, 14, 9, 0, 0),
            end_time=None
        )

        # 1. Fetch daily view
        daily_timeline = await self.timeline_engine.generate_timeline(session_id, "daily", start_date=self.ref_time)
        self.assertEqual(len(daily_timeline), 2)
        self.assertEqual(daily_timeline[0]["title"], "Daily Standup")
        self.assertEqual(daily_timeline[1]["title"], "Code Review")

        # 2. Fetch weekly view (includes milestone on 14th)
        weekly_timeline = await self.timeline_engine.generate_timeline(session_id, "weekly", start_date=self.ref_time)
        self.assertEqual(len(weekly_timeline), 3)

        # 3. Test delete
        deleted = await self.event_repo.delete_event(evt1["id"])
        self.assertTrue(deleted)
        
        # Confirm deleted from daily view
        daily_timeline_post = await self.timeline_engine.generate_timeline(session_id, "daily", start_date=self.ref_time)
        self.assertEqual(len(daily_timeline_post), 1)
        self.assertEqual(daily_timeline_post[0]["title"], "Code Review")

if __name__ == "__main__":
    unittest.main()
