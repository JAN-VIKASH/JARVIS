"""
Unit and integration tests for Reconciled Phase 5 Capabilities (Memory Lifecycle, Summarization, Compression, Adaptive Scorer, and Cognitive Reasoner).
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import text
from app.database.migrations import init_db
from app.database.session import get_async_session
from app.database.models import (
    UserFactModel, PreferenceModel, GoalModel, TaskModel, NoteModel, ConversationModel
)
from app.config.settings import settings
from app.services.factory import ServiceFactory
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.models.chat_models import ChatRequest
from memory.memory_factory import MemoryFactory
from memory.scorer import AdaptiveImportanceLearner

class MockLLM(BaseLLM):
    """
    Mock LLM implementation for testing.
    """
    def __init__(self):
        super().__init__()
        self.responses = []
        self.calls = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        return "Mock summary note content."

    async def generate_response(self, request, system_prompt, history=None, stream=False, config=None):
        self.calls.append(system_prompt)
        from app.models.chat_models import LLMResult
        return LLMResult(
            response="Mock Chat Response",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            provider="mock",
            model="mock",
            latency=0.1
        )

class TestReconciledPhase5(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        
        # Clean tables before tests
        async with get_async_session() as session:
            for tbl in ["conversations", "user_facts", "preferences", "goals", "tasks", "notes"]:
                await session.execute(text(f"DELETE FROM {tbl}"))
            await session.commit()
            
        self.memory_service = MemoryFactory.get_memory_service()
        self.sqlite_repo = MemoryFactory.get_sqlite_repo()
        self.task_service = ServiceFactory.get_task_service()
        
        self.mock_llm = MockLLM()
        self.summary_service = ServiceFactory.get_memory_summary_service()
        self.summary_service.llm = self.mock_llm
        
        self.cognitive_reasoner = ServiceFactory.get_cognitive_reasoner()
        self.cognitive_reasoner.llm = self.mock_llm

    async def test_note_and_goal_versioning(self):
        # 1. Create a note and save it
        note1 = await self.sqlite_repo.save_note(title="Meeting notes", content="Draft", importance=50)
        self.assertEqual(note1["version"], 1)

        # 2. Update it and check version increments
        note2 = await self.sqlite_repo.save_note(title="Meeting notes", content="Final draft", importance=50)
        self.assertEqual(note2["version"], 2)

        # 3. Create a goal and save it
        goal1 = await self.sqlite_repo.save_goal(title="Learn Python", description="Intro", status="active", importance=40)
        self.assertEqual(goal1["version"], 1)

        # 4. Update it and check version increments
        goal2 = await self.sqlite_repo.save_goal(title="Learn Python", description="Intro & OOP", status="active", importance=40)
        self.assertEqual(goal2["version"], 2)

    async def test_memory_lifecycle_apis(self):
        # Create fact
        fact = await self.sqlite_repo.save_fact(category="general", key="hobby", value="chess", confidence=1.0, importance=50)
        fact_id = fact["id"]
        
        # 1. Archive memory
        success = await self.memory_service.archive_memory(m_type="fact", record_id=fact_id, is_archived=True)
        self.assertTrue(success)
        db_fact = await self.sqlite_repo.get_record_by_id_and_type("fact", fact_id)
        self.assertTrue(db_fact["is_archived"])

        # 2. Reactivate/Restore memory
        success = await self.memory_service.archive_memory(m_type="fact", record_id=fact_id, is_archived=False)
        self.assertTrue(success)
        db_fact = await self.sqlite_repo.get_record_by_id_and_type("fact", fact_id)
        self.assertFalse(db_fact["is_archived"])

        # 3. Deactivate memory
        success = await self.memory_service.set_active_status(m_type="fact", record_id=fact_id, is_active=False)
        self.assertTrue(success)
        db_fact = await self.sqlite_repo.get_record_by_id_and_type("fact", fact_id)
        self.assertFalse(db_fact["is_active"])

        # 4. Delete memory permanently
        success = await self.memory_service.delete_memory_permanently(m_type="fact", record_id=fact_id)
        self.assertTrue(success)
        db_fact = await self.sqlite_repo.get_record_by_id_and_type("fact", fact_id)
        self.assertIsNone(db_fact)

    async def test_access_tracking_and_adaptive_importance(self):
        # Create a preference
        pref = await self.sqlite_repo.save_preference(category="tech", key="editor", value="vscode", confidence=1.0, importance=40)
        pref_id = pref["id"]
        
        # Access track search simulates retrieval matches
        matched_records = [{
            "memory_type": "preference",
            "record_id": pref_id,
            "similarity": 0.8
        }]
        
        # 1. Run access tracking under default search (query contains no explicit signals)
        await self.memory_service.track_access_and_learn(query="editor check", retrieved_records=matched_records)
        
        db_pref = await self.sqlite_repo.get_record_by_id_and_type("preference", pref_id)
        self.assertEqual(db_pref["access_count"], 1)
        self.assertIsNotNone(db_pref["last_accessed_at"])
        # No keyword boost, relevance boost adds (relevance*10 = 0.8*10 = 8) -> 40 + 8 = 48
        self.assertEqual(db_pref["importance"], 48)

        # 2. Run access tracking with explicit keyword signals
        await self.memory_service.track_access_and_learn(query="editor check remember this is crucial", retrieved_records=matched_records)
        
        db_pref = await self.sqlite_repo.get_record_by_id_and_type("preference", pref_id)
        self.assertEqual(db_pref["access_count"], 2)
        # Explicit signal boost adds +15, relevance adds +8 -> 48 + 23 = 71
        self.assertEqual(db_pref["importance"], 71)

        # 3. Repeated access tracking to verify bounding ceiling prevents runaway inflation
        for _ in range(20):
            await self.memory_service.track_access_and_learn(query="editor check", retrieved_records=matched_records)
            
        db_pref = await self.sqlite_repo.get_record_by_id_and_type("preference", pref_id)
        # Access count boost caps at +15. Relevance caps at +10. Explicit adds +0.
        # It should cap nicely below 100 or raise controlled step-wise.
        self.assertTrue(db_pref["importance"] <= 100)

    async def test_memory_summarization(self):
        # Prepopulate dialogue history
        await self.sqlite_repo.save_conversation("sess_1", "user", "What is Python?")
        await self.sqlite_repo.save_conversation("sess_1", "assistant", "A programming language.")
        
        self.mock_llm.responses.append("Python is a dynamic programming language.")
        
        summary = await self.summary_service.summarize_session_dialogue("sess_1")
        self.assertEqual(summary, "Python is a dynamic programming language.")
        
        # Verify saved note summary
        notes = await self.sqlite_repo.search_notes("Summary of Session")
        self.assertTrue(len(notes) >= 1)
        self.assertEqual(notes[0]["content"], "Python is a dynamic programming language.")

    async def test_safe_history_compression(self):
        # Prepopulate 45 messages (exceeds threshold 40)
        for i in range(22):
            await self.sqlite_repo.save_conversation("sess_compress", "user", f"Message {i}")
            await self.sqlite_repo.save_conversation("sess_compress", "assistant", f"Reply {i}")
        await self.sqlite_repo.save_conversation("sess_compress", "user", "Final trigger message")
            
        initial_count = await self.sqlite_repo.get_conversation_count("sess_compress")
        self.assertEqual(initial_count, 45)
        
        # Configure settings override
        settings.COMPRESSION_THRESHOLD = 40
        settings.COMPRESSION_TARGET = 20
        
        self.mock_llm.responses.append("Compressed dialogue of oldest chat messages.")
        
        # 1. Success Flow
        summary = await self.summary_service.compress_session_history("sess_compress")
        self.assertEqual(summary, "Compressed dialogue of oldest chat messages.")
        
        # Verify pruned dialogues (remaining should be exactly 20)
        final_count = await self.sqlite_repo.get_conversation_count("sess_compress")
        self.assertEqual(final_count, 20)
        
        # Verify summary note persisted
        notes = await self.sqlite_repo.search_notes("Compressed Dialogue History")
        self.assertTrue(len(notes) >= 1)
        self.assertEqual(notes[0]["content"], "Compressed dialogue of oldest chat messages.")

        # 2. Failure-Safe Flow
        # Setup another set exceeding threshold
        for i in range(15):
            await self.sqlite_repo.save_conversation("sess_compress_fail", "user", f"Msg {i}")
            await self.sqlite_repo.save_conversation("sess_compress_fail", "assistant", f"Rep {i}")
            
        fail_count_before = await self.sqlite_repo.get_conversation_count("sess_compress_fail")
        self.assertEqual(fail_count_before, 30) # let's set threshold to 25 to force trigger
        settings.COMPRESSION_THRESHOLD = 25
        settings.COMPRESSION_TARGET = 10
        
        # Simulate LLM failure by emptying responses and making generate raise Exception
        self.mock_llm.responses = []
        original_generate = self.mock_llm.generate
        
        async def fail_generate(prompt):
            raise RuntimeError("LLM Timeout or Connection Error")
        self.mock_llm.generate = fail_generate
        
        # Compress and ensure it returns None due to LLM error
        summary_fail = await self.summary_service.compress_session_history("sess_compress_fail")
        self.assertIsNone(summary_fail)
        
        # Verify raw dialogues are completely preserved intact (none deleted!)
        fail_count_after = await self.sqlite_repo.get_conversation_count("sess_compress_fail")
        self.assertEqual(fail_count_after, fail_count_before)
        
        # Restore mock llm method
        self.mock_llm.generate = original_generate

    async def test_cognitive_reasoner_and_context_budgeting(self):
        # 1. Adaptive Token Budgeting check
        # Task intent
        budgets_task = self.cognitive_reasoner.context_builder.build_adaptive_context(
            intent="task_query",
            user_profile={"name": "Alice"},
            direct_memories=["Prefers python", "Likes coffee"],
            semantic_memories=["Msg 1", "Msg 2"],
            task_context=["Task 1: Code review", "Task 2: Buy milk"]
        )
        # Verify tasks gets significant allocation
        self.assertIn("Task 1: Code review", budgets_task["task_context"])
        
        # Schedule intent
        budgets_schedule = self.cognitive_reasoner.context_builder.build_adaptive_context(
            intent="schedule_query",
            user_profile={"name": "Alice"},
            timeline_events=["Event 1: Meeting today", "Event 2: Lunch tomorrow"]
        )
        self.assertIn("Event 1: Meeting today", budgets_schedule["timeline_context"])
        
        # 2. Reason over context orchestration check
        context = await self.cognitive_reasoner.reason_over_context(
            query="show my pending tasks",
            session_id="sess_reason",
            intent="task_query"
        )
        self.assertIn("task_context", context)
        self.assertIn("profile_context", context)
