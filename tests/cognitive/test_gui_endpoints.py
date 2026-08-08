import os
import json
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.gui_bus import GUIEventBus
from voice.config import voice_settings
from app.agent.models import AgentPlan, AgentStep
from app.services.factory import ServiceFactory

class TestGUIEndpoints(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = TestClient(app)
        GUIEventBus._subscribers.clear()

    async def test_settings_get_masking(self):
        response = self.client.get("/api/v1/gui/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("WAKE_WORD_ENABLED", data)
        self.assertIn("WAKE_WORD_THRESHOLD", data)
        self.assertNotIn("GROQ_API_KEY", data)
        self.assertNotIn("OPENAI_API_KEY", data)

    async def test_settings_post_allowlist_validation(self):
        # Reject unauthorized keys
        response = self.client.post("/api/v1/gui/settings", json={"GROQ_API_KEY": "unauthorized"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unauthorized configuration modification", response.json()["detail"])
        
        # Allow allowlisted keys
        original = voice_settings.WAKE_WORD_ENABLED
        try:
            response2 = self.client.post("/api/v1/gui/settings", json={"WAKE_WORD_ENABLED": True})
            self.assertEqual(response2.status_code, 200)
            self.assertTrue(voice_settings.WAKE_WORD_ENABLED)
        finally:
            voice_settings.WAKE_WORD_ENABLED = original

    async def test_settings_persistence(self):
        from app.api.v1.gui_endpoints import update_env_file
        temp_env = ".env"
        backup = ""
        if os.path.exists(temp_env):
            with open(temp_env, "r", encoding="utf-8") as f:
                backup = f.read()

        try:
            with open(temp_env, "w", encoding="utf-8") as f:
                f.write("GROQ_API_KEY=keep_me_intact\nWAKE_WORD_ENABLED=False\n")

            update_env_file({"WAKE_WORD_ENABLED": True, "WAKE_WORD_THRESHOLD": 0.65})

            with open(temp_env, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("WAKE_WORD_ENABLED=True", content)
            self.assertIn("WAKE_WORD_THRESHOLD=0.65", content)
            self.assertIn("GROQ_API_KEY=keep_me_intact", content)
        finally:
            with open(temp_env, "w", encoding="utf-8") as f:
                f.write(backup)

    async def test_sse_subscription_and_delivery(self):
        queue = await GUIEventBus.subscribe()
        self.assertEqual(len(GUIEventBus._subscribers), 1)

        GUIEventBus.publish("voice_status", {"active": True, "state": "listening"})

        event = await queue.get()
        self.assertEqual(event["type"], "voice_status")
        self.assertEqual(event["data"]["state"], "listening")

        await GUIEventBus.unsubscribe(queue)
        self.assertEqual(len(GUIEventBus._subscribers), 0)

    async def test_bounded_queue_behavior_and_non_blocking(self):
        queue = await GUIEventBus.subscribe()
        
        # Publish 105 events (exceeds maxsize=100)
        for i in range(105):
            GUIEventBus.publish("test_event", {"val": i})

        self.assertEqual(queue.qsize(), 100)
        first_el = await queue.get()
        self.assertEqual(first_el["type"], "test_event")

        await GUIEventBus.unsubscribe(queue)

    async def test_voice_service_state_publication(self):
        from voice.session import VoiceSession
        session = VoiceSession()

        queue = await GUIEventBus.subscribe()

        session.start_recording()
        event = await queue.get()
        self.assertEqual(event["type"], "voice_status")
        self.assertEqual(event["data"]["state"], "listening")

        session.set_speaking()
        event2 = await queue.get()
        self.assertEqual(event2["data"]["state"], "speaking")

        await GUIEventBus.unsubscribe(queue)

    async def test_agent_executor_state_publication(self):
        from app.agent.executor import ExecutionEngine
        mock_desk = MagicMock()
        engine = ExecutionEngine(mock_desk)

        plan = AgentPlan(
            plan_id="test_plan_id_123",
            goal="Test Goal",
            created_at=12345.0,
            updated_at=12345.0,
            steps=[
                AgentStep(step_id=1, description="Step 1", selected_tool="launch_app", parameters={})
            ]
        )

        queue = await GUIEventBus.subscribe()

        engine._publish_agent_update(plan)

        event = await queue.get()
        self.assertEqual(event["type"], "agent_status")
        self.assertEqual(event["data"]["goal"], "Test Goal")
        self.assertEqual(event["data"]["steps"][0]["description"], "Step 1")

        await GUIEventBus.unsubscribe(queue)
