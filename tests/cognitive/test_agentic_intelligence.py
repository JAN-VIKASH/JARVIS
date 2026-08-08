"""
Comprehensive tests for JARVIS Phase 7 Agentic Intelligence.
All OS actions and LLM responses are mocked to prevent physical OS impacts.
"""
import asyncio
import unittest
import time
from typing import Dict, Any, List, Optional
from sqlalchemy import text

from app.database.migrations import init_db
from app.database.session import get_async_session
from app.services.factory import ServiceFactory
from app.services.llm.base import BaseLLM
from app.models.chat_models import LLMResult
from tools.desktop_tool import DesktopAutomationTool
from app.services.desktop_automation_service import DesktopAutomationService
from app.agent.core import AgentService
from app.agent.models import AgentPlan, AgentStep

class MockAgentLLM(BaseLLM):
    """
    Mock LLM to queue structured planner responses.
    """
    def __init__(self):
        super().__init__()
        self.responses = []
        self.calls = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        return '{"steps": []}'

    async def generate_response(self, request, system_prompt, history=None, stream=False, config=None):
        self.calls.append(system_prompt)
        text_resp = self.responses.pop(0) if self.responses else '{"steps": []}'
        return LLMResult(
            response=text_resp,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            provider="mock",
            model="mock",
            latency=0.1
        )

class TestAgenticIntelligence(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        # Clean tables
        async with get_async_session() as session:
            for tbl in ["conversations", "tasks", "notes", "goals"]:
                await session.execute(text(f"DELETE FROM {tbl}"))
            await session.commit()

        # Build clean test services with dry-run/mock setup
        self.mock_llm = MockAgentLLM()
        self.cognitive_reasoner = ServiceFactory.get_cognitive_reasoner()
        self.desktop_tool = DesktopAutomationTool(dry_run=True)
        self.desktop_service = DesktopAutomationService(llm=self.mock_llm, desktop_tool=self.desktop_tool)
        
        self.agent_service = AgentService(
            llm=self.mock_llm,
            cognitive_reasoner=self.cognitive_reasoner,
            desktop_service=self.desktop_service
        )

    async def test_simple_plan_generation_and_execution(self):
        # 1. Queue a simple 2-step plan
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Adjust system volume",
              "selected_tool": "set_volume",
              "parameters": {"level": 50},
              "prerequisites": []
            },
            {
              "step_id": 2,
              "description": "Type welcome message",
              "selected_tool": "type_text",
              "parameters": {"text": "hello from agent"},
              "prerequisites": [1]
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        
        session_id = "agent_sess_1"
        result = await self.agent_service.execute_goal("set volume to 50 then type hello from agent", session_id)
        
        # Verify plan outcomes
        self.assertEqual(result, "Goal completed successfully.")
        
        # Verify plan state stored in active_plans
        plans = list(self.agent_service.active_plans.values())
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].status, "SUCCESS")
        self.assertEqual(plans[0].steps[0].status, "COMPLETED")
        self.assertEqual(plans[0].steps[1].status, "COMPLETED")

    async def test_invalid_tool_rejection(self):
        # Plan contains unknown tool
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Delete windows config",
              "selected_tool": "format_c_drive",
              "parameters": {},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        result = await self.agent_service.execute_goal("run format", "agent_sess_2")
        self.assertIn("Agent execution failed", result)
        self.assertIn("Unknown tool", result)

    async def test_invalid_parameters_rejection(self):
        # Missing required app_name parameter for launch_app
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Launch something",
              "selected_tool": "launch_app",
              "parameters": {},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        result = await self.agent_service.execute_goal("launch app", "agent_sess_3")
        self.assertIn("Agent execution failed", result)
        self.assertIn("Missing required parameter", result)

    async def test_prerequisite_blocking_propagation(self):
        # Step 2 depends on Step 1, which fails due to bad parameters
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Launch app missing param",
              "selected_tool": "launch_app",
              "parameters": {},
              "prerequisites": []
            },
            {
              "step_id": 2,
              "description": "Type text",
              "selected_tool": "type_text",
              "parameters": {"text": "hello"},
              "prerequisites": [1]
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        result = await self.agent_service.execute_goal("launch then type", "agent_sess_4")
        self.assertIn("failed", result.lower())
        
        plan = list(self.agent_service.active_plans.values())[0]
        self.assertEqual(plan.steps[0].status, "FAILED")
        # Step 2 should be blocked because Step 1 failed
        self.assertEqual(plan.steps[1].status, "BLOCKED")

    async def test_dangerous_tool_safety_blocking(self):
        # Plan contains type_text with shell injection patterns (blocked safety classification)
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Run shell script",
              "selected_tool": "type_text",
              "parameters": {"text": "rm -rf /"},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        result = await self.agent_service.execute_goal("delete files", "agent_sess_5")
        self.assertIn("blocked", result.lower())
        
        plan = list(self.agent_service.active_plans.values())[0]
        self.assertEqual(plan.steps[0].status, "FAILED")
        self.assertIn("Safety Block", plan.steps[0].error)

    async def test_human_confirmation_and_approval_yes_no(self):
        # Step 1: launch_app notepad requires confirmation
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Launch notepad",
              "selected_tool": "launch_app",
              "parameters": {"app_name": "notepad"},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        session_id = "agent_confirm_sess"
        
        # 1. First execution prompts for confirmation and pauses loop
        result = await self.agent_service.execute_goal("open notepad", session_id)
        self.assertIn("I need your confirmation", result)
        
        plan = list(self.agent_service.active_plans.values())[0]
        self.assertEqual(plan.status, "WAITING_FOR_CONFIRMATION")
        self.assertEqual(plan.steps[0].status, "RUNNING")
        
        # 2. User confirms with "yes" -> loop resumes and succeeds
        res_yes = await self.agent_service.execute_goal("yes", session_id)
        self.assertEqual(res_yes, "Goal completed successfully.")
        self.assertEqual(plan.status, "SUCCESS")
        self.assertEqual(plan.steps[0].status, "COMPLETED")

    async def test_human_confirmation_rejection(self):
        # Step requires confirmation
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Launch notepad",
              "selected_tool": "launch_app",
              "parameters": {"app_name": "notepad"},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        session_id = "agent_cancel_sess"
        
        await self.agent_service.execute_goal("open notepad", session_id)
        
        # User replies "no" -> plan transitions to FAILED and step to CANCELLED
        res_no = await self.agent_service.execute_goal("no", session_id)
        self.assertEqual(res_no, "Plan execution cancelled.")
        
        plan = list(self.agent_service.active_plans.values())[0]
        self.assertEqual(plan.status, "FAILED")
        self.assertEqual(plan.steps[0].status, "CANCELLED")

    async def test_bounded_retry_and_recovery_flow(self):
        # Verification check will fail first, recovery refocus strategy runs, succeeds on 2nd attempt
        plan_json = """
        {
          "steps": [
            {
              "step_id": 1,
              "description": "Type text on focused window",
              "selected_tool": "type_text",
              "parameters": {"text": "recovery works", "target_window": "notepad"},
              "prerequisites": []
            }
          ]
        }
        """
        self.mock_llm.responses.append(plan_json)
        
        # Mock type_text to fail verification on the first attempt by throwing exception, and pass subsequently
        original_run = self.desktop_service._run_tool_command
        calls = []
        
        async def mock_run_tool_cmd(command, parameters):
            calls.append(parameters)
            if len(calls) == 1:
                # Force failure on first try
                return "Error: window focus failed"
            return "Typed text successfully"
            
        self.desktop_service._run_tool_command = mock_run_tool_cmd
        
        session_id = "agent_retry_sess"
        result = await self.agent_service.execute_goal("type on notepad", session_id)
        
        # Verify success after retry recovery
        self.assertEqual(result, "Goal completed successfully.")
        plan = list(self.agent_service.active_plans.values())[0]
        self.assertEqual(plan.steps[0].status, "COMPLETED")
        self.assertEqual(plan.steps[0].retry_count, 1)
        
        # Restore mock
        self.desktop_service._run_tool_command = original_run
