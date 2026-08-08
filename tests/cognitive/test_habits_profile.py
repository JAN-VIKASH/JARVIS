import asyncio
import json
import unittest
from typing import List, Dict, Any, Optional

from app.database.migrations import init_db
from app.database.session import get_async_session
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.cognitive.profile.user_profile_engine import UserProfileEngine
from memory.memory_factory import MemoryFactory
from sqlalchemy import text

class MockLLMForHabits(BaseLLM):
    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        msg = request.message.lower()
        if "every night" in msg or "always" in msg:
            resp = json.dumps({
                "updates": [
                    {"key": "habits", "operation": "add", "value": "study Java nightly", "confidence": 0.95}
                ]
            })
        else:
            # Single occurrence query, should not extract habit
            resp = json.dumps({
                "updates": []
            })
            
        return LLMResult(
            response=resp,
            provider="mock",
            model="mock",
            latency=0.002,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20
        )

class TestHabitsProfile(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        
        # Clean profiles table
        async with get_async_session() as session:
            await session.execute(text("DELETE FROM user_profiles"))
            await session.commit()
            
        self.profile_repo = MemoryFactory.get_user_profile_repo()
        self.mock_llm = MockLLMForHabits()
        self.profile_engine = UserProfileEngine(profile_repo=self.profile_repo, llm=self.mock_llm)

    async def test_extract_habit_success(self):
        session_id = "habit_session"
        
        # 1. Test recurring input (extracts habit)
        await self.profile_engine.extract_and_update_profile(
            text="Remember that I study Java every night.",
            session_id=session_id
        )
        
        prof = await self.profile_engine.get_profile_context(session_id)
        self.assertIn("habits", prof)
        self.assertIn("study Java nightly", prof["habits"])

    async def test_ignore_single_occurrence(self):
        session_id = "single_occ_session"
        
        # 2. Test single occurrence (ignored by LLM response mock)
        await self.profile_engine.extract_and_update_profile(
            text="I studied Python yesterday.",
            session_id=session_id
        )
        
        prof = await self.profile_engine.get_profile_context(session_id)
        self.assertNotIn("habits", prof)
        self.assertNotIn("routines", prof)
