"""
Unit and integration tests for Phase 8 Browser Automation capabilities.
Tests Safety Tiers, direct execution, confirmation loops, and path validations.
"""
import unittest
import time
from typing import Dict, Any, Optional

from app.services.browser_automation_service import BrowserAutomationService
from app.services.factory import ServiceFactory
from app.services.chat_service import ChatService
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.database.migrations import init_db

class MockBrowserLLM(BaseLLM):
    async def generate(self, prompt: str) -> str:
        return "Mock response"
        
    async def generate_response(self, request, system_prompt, history=None, stream=False, config=None):
        msg = request.message.lower()
        resp = "{}"
        if "navigate to" in msg or "go to" in msg:
            resp = '{"command": "navigate_url", "parameters": {"url": "https://google.com"}}'
        elif "click button" in msg:
            resp = '{"command": "click_element", "parameters": {"selector": "#submit-btn"}}'
        elif "download" in msg:
            resp = '{"command": "download_file", "parameters": {"url": "https://example.com/file.pdf"}}'
        elif "yes" in msg:
            resp = "yes"
            
        return LLMResult(
            response=resp,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            provider="mock",
            model="mock",
            latency=0.1
        )

class MockBrowserService(BrowserAutomationService):
    def __init__(self, llm: Optional[Any] = None, testing: bool = True):
        super().__init__(llm=llm, testing=testing)
        # Populate mock session context
        self.sessions = {
            "sess_browser": {
                "pages": [object()],
                "active_page_index": 0,
                "last_accessed": time.time()
            }
        }

    async def initialize(self):
        pass

    async def close(self):
        pass

    async def _run_browser_action(self, session_id: str, command: str, parameters: Dict[str, Any]) -> str:
        if command == "open_browser":
            return "Browser session is active and page tab focused."
        elif command == "navigate_url":
            return f"[Mock] Navigated successfully to '{parameters['url']}'."
        elif command == "click_element":
            return f"[Mock] Clicked element: '{parameters['selector']}'"
        elif command == "type_element":
            return f"[Mock] Typed text into element: '{parameters['selector']}'"
        elif command == "scroll_browser":
            return f"[Mock] Scrolled page {parameters['direction']}."
        elif command == "read_page_content":
            return "Extracted Content:\nMock Text Data"
        elif command == "switch_tab":
            return "[Mock] Switched tab."
        elif command == "close_tab":
            return "[Mock] Closed tab."
        elif command == "download_file":
            return f"[Mock] Downloaded successfully to '{parameters['url']}'."
        elif command == "upload_file":
            return f"[Mock] Uploaded successfully: '{parameters['file_path']}'."
        return "Unsupported."

class TestBrowserAutomation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.llm = MockBrowserLLM()
        self.browser_service = MockBrowserService(llm=self.llm, testing=True)
        
        # Patch service singleton inside ServiceFactory
        ServiceFactory._browser_automation_service = self.browser_service
        self.chat_service = ChatService(llm=self.llm)

    async def test_safety_classification_tiers(self):
        # 1. SAFE command run immediately
        res_nav = await self.browser_service.execute_browser_command(
            "sess_browser", "navigate_url", {"url": "https://google.com"}
        )
        self.assertIn("[Mock] Navigated successfully to", res_nav)

        # 2. CAUTION command run immediately
        res_click = await self.browser_service.execute_browser_command(
            "sess_browser", "click_element", {"selector": ".btn-next"}
        )
        self.assertIn("[Mock] Clicked element", res_click)

        # 3. CONFIRMATION_REQUIRED command (download_file) cached
        res_download = await self.browser_service.execute_browser_command(
            "sess_browser", "download_file", {"url": "https://example.com/data.csv"}
        )
        self.assertIn("confirmation", res_download.lower())
        self.assertIn("sess_browser", self.browser_service._pending_confirmations)

        # 4. BLOCKED command (non-whitelisted scheme)
        res_blocked = await self.browser_service.execute_browser_command(
            "sess_browser", "navigate_url", {"url": "file:///etc/passwd"}
        )
        self.assertIn("blocked due to safety restrictions", res_blocked.lower())

        # 5. BLOCKED localhost in prod mode (testing = False)
        prod_service = MockBrowserService(testing=False)
        res_local = await prod_service.execute_browser_command(
            "sess_browser", "navigate_url", {"url": "http://localhost:8080"}
        )
        self.assertIn("blocked due to safety restrictions", res_local.lower())

        # 6. ALLOWED localhost in test mode (testing = True)
        res_local_test = await self.browser_service.execute_browser_command(
            "sess_browser", "navigate_url", {"url": "http://localhost:8080"}
        )
        self.assertIn("[Mock] Navigated successfully to", res_local_test)

    async def test_file_path_validation_boundaries(self):
        # 1. Valid filename under download dir
        valid, result = self.browser_service.validate_file_path("report.pdf")
        self.assertTrue(valid)
        self.assertTrue(result.endswith("report.pdf"))

        # 2. Blocked absolute path outside download dir
        valid, result = self.browser_service.validate_file_path("C:\\Windows\\System32\\cmd.exe")
        self.assertFalse(valid)
        self.assertIn("Access Denied", result)

        # 3. Blocked path traversal attempt
        valid, result = self.browser_service.validate_file_path("../passwords.txt")
        self.assertFalse(valid)
        self.assertIn("Access Denied", result)

        # 4. Blocked dangerous executable extension
        valid, result = self.browser_service.validate_file_path("payload.exe")
        self.assertFalse(valid)
        self.assertIn("Access Denied", result)

    async def test_confirmation_yes_no_flow(self):
        # Trigger navigation to confirmation required action (download)
        await self.browser_service.execute_action("sess_yes", "download data.csv")
        self.assertIn("sess_yes", self.browser_service._pending_confirmations)

        # Confirm "yes"
        res_yes = await self.browser_service.execute_action("sess_yes", "yes")
        self.assertIn("[Mock] Downloaded successfully", res_yes)
        self.assertNotIn("sess_yes", self.browser_service._pending_confirmations)

        # Reject "no"
        await self.browser_service.execute_action("sess_no", "download data.csv")
        res_no = await self.browser_service.execute_action("sess_no", "no")
        self.assertEqual(res_no, "Action cancelled.")
        self.assertNotIn("sess_no", self.browser_service._pending_confirmations)

    async def test_chat_service_routing(self):
        req = ChatRequest(session_id="sess_chat_int", message="navigate to https://google.com")
        res = await self.chat_service.execute_chat(req)
        self.assertIn("[Mock] Navigated successfully", res)
