"""
Unit and integration tests for Phase 6 Desktop Automation.
Uses a mock desktop automation tool to prevent physical hardware interactions.
"""
import asyncio
import unittest
import time
from typing import List, Dict, Any, Optional

from app.database.migrations import init_db
from app.database.session import get_async_session
from app.services.factory import ServiceFactory
from app.services.chat_service import ChatService
from app.models.chat_models import ChatRequest
from app.services.response.intent_classifier import IntentClassifier
from app.services.desktop_automation_service import DesktopAutomationService
from tools.desktop_tool import DesktopAutomationTool


class MockDesktopAutomationTool(DesktopAutomationTool):
    """
    Subclass of DesktopAutomationTool that stubs out all GUI operations and records calls.
    """
    def __init__(self):
        super().__init__(dry_run=True)
        self.calls: List[Dict[str, Any]] = []

    def move_mouse(self, x: int, y: int) -> str:
        self.calls.append({"command": "move_mouse", "x": x, "y": y})
        return f"[Mock] Moved mouse to ({x}, {y})"

    def click_mouse(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        self.calls.append({"command": "click_mouse", "x": x, "y": y, "button": button, "clicks": clicks})
        return f"[Mock] Clicked mouse {button} at ({x}, {y})"

    def focus_window(self, title: str) -> str:
        self.calls.append({"command": "focus_window", "title": title})
        return f"[Mock] Focused window: '{title}'"

    def type_text(self, text: str, target_window: Optional[str] = None) -> str:
        self.calls.append({"command": "type_text", "text": text, "target_window": target_window})
        return f"[Mock] Typed text: '{text}' in target window: '{target_window}'"

    def press_key(self, key: str) -> str:
        self.calls.append({"command": "press_key", "key": key})
        return f"[Mock] Pressed key: '{key}'"

    def hotkey(self, keys: List[str]) -> str:
        self.calls.append({"command": "hotkey", "keys": keys})
        return f"[Mock] Executed hotkey combination: {keys}"

    def list_windows(self) -> List[str]:
        self.calls.append({"command": "list_windows"})
        return ["[Mock] Notepad", "[Mock] Chrome"]

    def close_window(self, title: str) -> str:
        self.calls.append({"command": "close_window", "title": title})
        return f"[Mock] Closed window matching: '{title}'"

    def launch_app(self, app_name: str, args: Optional[List[str]] = None) -> str:
        self.calls.append({"command": "launch_app", "app_name": app_name, "args": args})
        return f"[Mock] Launched application: '{app_name}' successfully."

    def set_volume(self, level: int) -> str:
        self.calls.append({"command": "set_volume", "level": level})
        return f"[Mock] Set volume to {level}%"

    def lock_screen(self) -> str:
        self.calls.append({"command": "lock_screen"})
        return "[Mock] Screen locked successfully."

    def take_screenshot(self, dest_path: str = "scratch/screenshot.png") -> str:
        self.calls.append({"command": "take_screenshot", "dest_path": dest_path})
        return f"[Mock] Screenshot saved to {dest_path}"


class TestDesktopAutomation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.mock_tool = MockDesktopAutomationTool()
        
        # Instantiate service injecting mock tool
        # Resolves LLM mock/placeholder from factory
        self.llm = ServiceFactory.get_llm()
        self.desktop_service = DesktopAutomationService(llm=self.llm, desktop_tool=self.mock_tool)
        
        # Override the ServiceFactory singleton temporarily for integration tests
        ServiceFactory._desktop_automation_service = self.desktop_service
        self.chat_service = ChatService(llm=self.llm)

    async def test_classification_and_safety_tiers(self):
        # 1. SAFE command run immediately
        res_screenshot = await self.desktop_service.execute_action("sess_1", "take a screenshot")
        self.assertIn("[Mock] Screenshot saved", res_screenshot)
        self.assertEqual(len(self.mock_tool.calls), 1)
        self.assertEqual(self.mock_tool.calls[-1]["command"], "take_screenshot")

        # 2. CAUTION command run immediately
        res_mouse = await self.desktop_service.execute_action("sess_1", "move mouse to 500, 300")
        # Note: If LLM is fallback parsed or generated
        self.assertTrue("Moved mouse to" in res_mouse or "[Mock] Moved mouse" in res_mouse)

        # 3. CONFIRMATION_REQUIRED command (launch app notepad) cached
        res_confirm = await self.desktop_service.execute_action("sess_1", "open notepad")
        self.assertIn("confirmation", res_confirm.lower())
        self.assertIn("sess_1", self.desktop_service._pending_confirmations)
        # Verify it has NOT been run yet
        self.assertNotIn("launch_app", [c["command"] for c in self.mock_tool.calls])

        # 4. BLOCKED command
        res_blocked = await self.desktop_service.execute_action("sess_blocked", "delete file C:\\Windows\\System32")
        self.assertIn("blocked", res_blocked.lower())

    async def test_confirmation_yes_no_flow(self):
        # Trigger launch notepad -> confirmation required
        await self.desktop_service.execute_action("sess_yes", "open notepad")
        self.assertIn("sess_yes", self.desktop_service._pending_confirmations)
        
        # Send positive confirmation "yes"
        res_yes = await self.desktop_service.execute_action("sess_yes", "yes")
        self.assertIn("[Mock] Launched application", res_yes)
        # Verify notepad was executed
        self.assertEqual(self.mock_tool.calls[-1]["command"], "launch_app")
        self.assertEqual(self.mock_tool.calls[-1]["app_name"], "notepad")
        # Verify confirmation cleared
        self.assertNotIn("sess_yes", self.desktop_service._pending_confirmations)

        # Trigger launch chrome -> confirmation required
        await self.desktop_service.execute_action("sess_no", "open chrome")
        # Send negative confirmation "no"
        res_no = await self.desktop_service.execute_action("sess_no", "no")
        self.assertEqual(res_no, "Action cancelled.")
        self.assertNotIn("sess_no", self.desktop_service._pending_confirmations)

    async def test_confirmation_expiration(self):
        await self.desktop_service.execute_action("sess_expire", "open notepad")
        self.assertIn("sess_expire", self.desktop_service._pending_confirmations)
        
        # Override the timestamp to be 130 seconds in the past
        self.desktop_service._pending_confirmations["sess_expire"]["timestamp"] -= 130.0
        
        # Trigger pruning check via executing action
        res = await self.desktop_service.execute_action("sess_expire", "yes")
        # Confirmation has expired, so it doesn't process "yes" as a confirmation of notepad
        self.assertNotIn("sess_expire", self.desktop_service._pending_confirmations)
        self.assertNotIn("[Mock] Launched application", res)

    def test_intent_classifier_integration(self):
        intent_open = IntentClassifier.classify("Open notepad please")
        self.assertEqual(intent_open, "desktop_action")

        intent_click = IntentClassifier.classify("click mouse at 200, 400")
        self.assertEqual(intent_click, "desktop_action")

        intent_lock = IntentClassifier.classify("lock the workstation screen")
        self.assertEqual(intent_lock, "desktop_action")

    async def test_chat_service_routing_integration(self):
        req = ChatRequest(session_id="sess_chat_int", message="take a screenshot")
        res = await self.chat_service.execute_chat(req)
        self.assertIn("[Mock] Screenshot saved", res)
        self.assertEqual(self.mock_tool.calls[-1]["command"], "take_screenshot")
        
        # Test pending confirmation routing in execute_chat
        req_notepad = ChatRequest(session_id="sess_chat_int", message="open notepad")
        res_notepad = await self.chat_service.execute_chat(req_notepad)
        self.assertIn("confirmation", res_notepad.lower())
        
        # Confirming notepad
        req_confirm = ChatRequest(session_id="sess_chat_int", message="yes")
        res_confirm = await self.chat_service.execute_chat(req_confirm)
        self.assertIn("[Mock] Launched application", res_confirm)
