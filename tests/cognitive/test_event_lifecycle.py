import asyncio
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from app.database.migrations import init_db
from app.database.session import get_async_session
from app.database.models import EventMemoryModel
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.database.repositories.event_repository import EventRepository
from app.services.cognitive.time_normalizer import TimeNormalizer
from app.services.cognitive.event_extractor import EventExtractor
from app.services.cognitive.timeline_engine import TimelineEngine
from app.services.response.intent_classifier import IntentClassifier
from memory.memory_service import MemoryService
from memory.memory_factory import MemoryFactory
from memory.test_memory import clear_database

class MockLLMForLifecycle(BaseLLM):
    """
    Mock LLM provider representing updates, deletions, completions, and scheduling.
    """
    def __init__(self):
        self.operation = "CREATE"
        self.matched_event_id = None
        self.confidence = 0.95
        
    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        msg = request.message.lower()
        
        if "normalize this time phrase" in msg:
            if "tomorrow at 5pm" in msg or "tomorrow at 5 pm" in msg:
                resp = "2026-08-08T17:00:00"
            elif "friday" in msg:
                resp = "2026-08-14T17:00:00"
            else:
                resp = "2026-08-08T12:00:00"
        elif "extract events from" in msg:
            if "meeting tomorrow 5pm" in msg or "meeting tomorrow at 5 pm" in msg:
                resp = json.dumps([
                    {
                        "title": "Meeting Tomorrow",
                        "description": "Project sync",
                        "event_type": "meeting",
                        "start_time_phrase": "tomorrow at 5pm",
                        "end_time_phrase": None,
                        "is_all_day": False,
                        "importance": "high",
                        "confidence": 0.95
                    }
                ])
            elif "move it to friday" in msg:
                resp = json.dumps([
                    {
                        "title": "Meeting Tomorrow",
                        "description": "Project sync",
                        "event_type": "meeting",
                        "start_time_phrase": "Friday at 5pm",
                        "end_time_phrase": None,
                        "is_all_day": False,
                        "importance": "high",
                        "confidence": 0.95
                    }
                ])
            else:
                resp = "[]"
        elif "analyze input:" in msg:
            resp = json.dumps({
                "operation": self.operation,
                "matched_event_id": self.matched_event_id,
                "confidence": self.confidence
            })
        else:
            resp = "[]"
            
        return LLMResult(
            response=resp,
            provider="mock",
            model="mock",
            latency=0.005,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20
        )

class TestEventLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sqlalchemy import text
        async with get_async_session() as session:
            await session.execute(text("DROP TABLE IF EXISTS event_memories"))
            await session.commit()
        await init_db()
        await clear_database()
        self.mock_llm = MockLLMForLifecycle()
        self.event_repo = EventRepository()
        self.timeline_engine = TimelineEngine(self.event_repo)
        
        # Build memory service with mock components
        self.memory_service = MemoryFactory.get_memory_service()
        self.memory_service.event_repository = self.event_repo
        self.memory_service.event_extractor = EventExtractor(self.mock_llm)
        
        # Re-init advance lifecycle components with mock LLM
        from app.services.cognitive.event_update_detector import EventUpdateDetector
        from app.services.cognitive.duplicate_event_resolver import DuplicateEventResolver
        self.memory_service.event_update_detector = EventUpdateDetector(self.mock_llm, self.event_repo)
        self.memory_service.duplicate_resolver = DuplicateEventResolver(self.event_repo)
        
        self.session_id = "test_lifecycle_session"
        self.ref_time = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)

    async def test_repository_lifecycle_states_and_integrity(self):
        # 1. Test save planned event
        ev = await self.event_repo.save_event(
            session_id=self.session_id,
            title="Design Review",
            description="Discuss system architecture",
            event_type="meeting",
            start_time=datetime(2026, 8, 8, 10, 0, 0),
            end_time=None,
            is_all_day=False,
            status="planned",
            importance="high",
            confidence=0.9
        )
        self.assertEqual(ev["status"], "planned")
        self.assertEqual(ev["importance"], "high")
        self.assertEqual(ev["version"], 1)
        self.assertIsNone(ev["parent_event_id"])
        
        # 2. Test status updates (planned -> completed)
        ev_comp = await self.event_repo.update_event_status(ev["id"], "completed")
        self.assertEqual(ev_comp["status"], "completed")
        self.assertEqual(ev_comp["version"], 2)
        self.assertEqual(ev_comp["parent_event_id"], ev["id"])
        
        # 3. Test get overdue events (none since it is completed)
        overdues = await self.event_repo.get_overdue_events(self.session_id)
        self.assertEqual(len(overdues), 0)

    async def test_update_detection_and_version_history(self):
        # Initial creation
        self.mock_llm.operation = "CREATE"
        self.mock_llm.matched_event_id = None
        
        await self.memory_service.extract_and_save_events(self.session_id, "Meeting tomorrow 5pm")
        await asyncio.sleep(0.1) # Wait for background task
        
        # Fetch active upcoming events
        upcoming = await self.event_repo.get_upcoming_events(self.session_id)
        self.assertEqual(len(upcoming), 1)
        event_id = upcoming[0]["id"]
        
        # Simulate UPDATE detection ("move it to Friday")
        self.mock_llm.operation = "UPDATE"
        self.mock_llm.matched_event_id = event_id
        
        await self.memory_service.extract_and_save_events(self.session_id, "Actually move it to Friday.")
        await asyncio.sleep(0.1)
        
        # Confirm version history walks up correctly
        versions = await self.event_repo.get_event_versions(event_id)
        # Check active version is version 2 (and has parent_event_id == version 1 ID)
        active_events = await self.timeline_engine.generate_timeline(self.session_id, "all")
        self.assertEqual(len(active_events), 1)
        self.assertEqual(active_events[0]["version"], 2)
        self.assertEqual(active_events[0]["parent_event_id"], event_id)
        
        # revision count should walk up to version 2 (meaning length of chain is 2)
        history = await self.event_repo.get_event_versions(active_events[0]["id"])
        self.assertEqual(len(history), 2)

    async def test_duplicate_event_resolution(self):
        self.mock_llm.operation = "CREATE"
        
        # Save first event
        await self.memory_service.extract_and_save_events(self.session_id, "Meeting tomorrow 5pm")
        await asyncio.sleep(0.1)
        
        # Save same/similar event
        await self.memory_service.extract_and_save_events(self.session_id, "Meeting tomorrow at 5 PM")
        await asyncio.sleep(0.1)
        
        # Confirm only one logical event exists (version incremented/merged instead of duplicate appended)
        active_events = await self.timeline_engine.generate_timeline(self.session_id, "all")
        self.assertEqual(len(active_events), 1)
        self.assertEqual(active_events[0]["version"], 2)

    async def test_utc_handling_and_display(self):
        # Store naive UTC
        utc_time = datetime(2026, 8, 8, 17, 0, 0)
        ev = await self.event_repo.save_event(
            session_id=self.session_id,
            title="UTC Standup",
            description=None,
            event_type="meeting",
            start_time=utc_time,
            end_time=None
        )
        self.assertIsNone(ev["start_time"].tzinfo) # Stored naive in DB
        self.assertEqual(ev["start_time"], utc_time)

    async def test_intent_classification_rules(self):
        self.assertEqual(IntentClassifier.classify("What is my schedule tomorrow?"), "schedule_query")
        self.assertEqual(IntentClassifier.classify("What happened last week?"), "timeline_query")
        self.assertEqual(IntentClassifier.classify("When is my interview?"), "event_query")

    async def test_timeline_sorting_and_queries(self):
        # Populate events with different importances
        await self.event_repo.save_event(
            self.session_id, "Low Event", None, "task", datetime(2026, 8, 8, 9, 0), None, importance="low"
        )
        await self.event_repo.save_event(
            self.session_id, "High Event", None, "meeting", datetime(2026, 8, 8, 11, 0), None, importance="high"
        )
        await self.event_repo.save_event(
            self.session_id, "Medium Event", None, "deadline", datetime(2026, 8, 8, 10, 0), None, importance="medium"
        )
        
        # Fetch sorted by importance (high -> medium -> low)
        timeline = await self.timeline_engine.generate_timeline(
            self.session_id, view="all", sort_by="importance"
        )
        self.assertEqual(timeline[0]["title"], "High Event")
        self.assertEqual(timeline[1]["title"], "Medium Event")
        self.assertEqual(timeline[2]["title"], "Low Event")

    async def test_performance_latencies(self):
        # Measure pipeline execution time
        start_time = time.perf_counter()
        
        self.mock_llm.operation = "CREATE"
        await self.memory_service.extract_and_save_events(self.session_id, "Meeting tomorrow 5pm")
        await asyncio.sleep(0.05)
        
        elapsed = time.perf_counter() - start_time
        print(f"\n[Performance Latency Log] Advanced Event Pipeline execution time: {elapsed:.4f}s")
        # Ensure it runs safely asynchronously
        self.assertLess(elapsed, 0.5)

if __name__ == "__main__":
    unittest.main()
