"""
Browser Automation Service using Playwright async API.
Manages isolated browser contexts, safety tiers, confirmations, and file validations.
"""
import os
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.config.settings import settings

logger = logging.getLogger("jarvis.services.browser")

class BrowserAutomationService:
    """
    Coordinates browser sessions and controls navigation, clicking, typing, and tab isolation.
    """
    def __init__(self, llm: Optional[Any] = None, testing: bool = False):
        self.testing = testing
        self.llm = llm
        self.playwright = None
        self.browser: Optional[Browser] = None
        # session_id -> {
        #   "context": BrowserContext,
        #   "pages": List[Page],
        #   "active_page_index": int,
        #   "last_accessed": float
        # }
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 300.0  # 5 minutes of inactivity
        self.download_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../downloads"))
        
        # Ensure download folder exists
        os.makedirs(self.download_dir, exist_ok=True)

    async def initialize(self):
        """
        Initializes the async playwright driver.
        """
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            # Launch chromium headless in production, headful if config or testing requests it
            headless_mode = not self.testing
            self.browser = await self.playwright.chromium.launch(headless=headless_mode)
            # Start background inactivity scavenger
            asyncio.create_task(self._scavenge_inactive_sessions())

    async def close(self):
        """
        Closes active contexts and shuts down playwright client.
        """
        for sid in list(self.sessions.keys()):
            await self.close_session(sid)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _scavenge_inactive_sessions(self):
        """
        Scavenger daemon cleaning up idle sessions.
        """
        while self.playwright is not None:
            await asyncio.sleep(30.0)
            now = time.time()
            for sid, sdata in list(self.sessions.items()):
                if now - sdata["last_accessed"] > self.session_timeout:
                    logger.info(f"Closing idle browser session context for session: {sid}")
                    await self.close_session(sid)

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Resolves or initializes a session browser context.
        """
        await self.initialize()
        
        if session_id not in self.sessions:
            logger.info(f"Creating new isolated BrowserContext for session: {session_id}")
            context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                accept_downloads=True
            )
            # Open default page
            page = await context.new_page()
            self.sessions[session_id] = {
                "context": context,
                "pages": [page],
                "active_page_index": 0,
                "last_accessed": time.time()
            }
        else:
            self.sessions[session_id]["last_accessed"] = time.time()
            
        return self.sessions[session_id]

    async def close_session(self, session_id: str):
        if session_id in self.sessions:
            sdata = self.sessions.pop(session_id)
            try:
                await sdata["context"].close()
            except Exception as e:
                logger.warning(f"Error closing context for session {session_id}: {e}")

    async def get_active_page(self, session_id: str) -> Page:
        sdata = await self.get_session(session_id)
        idx = sdata["active_page_index"]
        if idx < len(sdata["pages"]):
            return sdata["pages"][idx]
        if sdata["pages"]:
            return sdata["pages"][0]
        # Fallback create a page
        page = await sdata["context"].new_page()
        sdata["pages"].append(page)
        sdata["active_page_index"] = 0
        return page

    def _classify_safety_tier(self, command: str, parameters: Dict[str, Any]) -> str:
        """
        Independent safety validation checks inside the service.
        """
        # Blocked commands
        blocked_commands = {"cookie_theft", "steal_token", "extract_credentials", "bypass_captcha"}
        if command in blocked_commands:
            return "BLOCKED"

        # Check URL constraints
        if "url" in parameters:
            url = str(parameters["url"]).strip().lower()
            if not (url.startswith("http://") or url.startswith("https://")):
                return "BLOCKED"
            if "localhost" in url or "127.0.0.1" in url:
                if not self.testing:
                    return "BLOCKED"

        # Check file validation constraints (independent enforcement)
        if "file_path" in parameters:
            fp = str(parameters["file_path"])
            is_valid, _ = self.validate_file_path(fp)
            if not is_valid:
                return "BLOCKED"

        # Safety classifications
        if command in ["open_browser", "scroll_browser", "read_page_content", "switch_tab"]:
            return "SAFE"
            
        if command == "navigate_url":
            return "SAFE"

        if command in ["click_element", "type_element", "close_tab"]:
            # Check element descriptors for sensitive clicks/submissions
            selector = str(parameters.get("selector", "")).lower()
            if any(kw in selector for kw in ["submit", "pay", "buy", "purchase", "transfer", "delete", "remove"]):
                return "CONFIRMATION_REQUIRED"
            return "CAUTION"

        if command in ["download_file", "upload_file"]:
            return "CONFIRMATION_REQUIRED"

        return "BLOCKED"

    def validate_file_path(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Ensures file paths are confined strictly to downloads/ folder and contain no dangerous extensions.
        """
        # Traverse protection
        if ".." in file_path or file_path.startswith("/") or (":" in file_path and not file_path.startswith(self.download_dir)):
            return False, "Access Denied: Path traversal or absolute paths outside downloads folder are blocked."

        # Compute target absolute path
        abs_path = os.path.abspath(os.path.join(self.download_dir, os.path.basename(file_path)))
        if not abs_path.startswith(self.download_dir):
            return False, "Access Denied: Destination path is outside the workspace downloads directory."

        # Check extensions
        ext = os.path.splitext(abs_path)[1].lower()
        dangerous_exts = {".exe", ".bat", ".ps1", ".sh", ".msi", ".cmd", ".vbs", ".scr"}
        if ext in dangerous_exts:
            return False, f"Access Denied: Extensions of type {ext} are blocked for security."

        return True, abs_path

    async def execute_browser_command(self, session_id: str, command: str, parameters: Dict[str, Any]) -> str:
        """
        Validates safety tiers, checks confirmations, and executes browser tool steps.
        """
        # 1. Enforce safety validation inside the service
        tier = self._classify_safety_tier(command, parameters)
        if tier == "BLOCKED":
            return "Executing this browser command is blocked due to safety restrictions. Access denied."

        if tier == "CONFIRMATION_REQUIRED":
            self._pending_confirmations[session_id] = {
                "command": command,
                "parameters": parameters,
                "timestamp": time.time()
            }
            return f"I need your confirmation to proceed with the action: [{command}] using parameters {parameters}. Please say 'yes' to confirm or 'no' to cancel."

        return await self._run_browser_action(session_id, command, parameters)

    async def _run_browser_action(self, session_id: str, command: str, parameters: Dict[str, Any]) -> str:
        """
        Underlying playwright controller executing actions.
        """
        page = await self.get_active_page(session_id)
        sdata = self.sessions[session_id]
        
        try:
            if command == "open_browser":
                # Ensure context exists
                return "Browser session is active and page tab focused."

            elif command == "navigate_url":
                url = parameters["url"]
                # Default timeout 15s
                await page.goto(url, timeout=15000)
                title = await page.title()
                return f"Navigated successfully to '{url}'. Page Title: '{title}'"

            elif command == "click_element":
                sel = parameters["selector"]
                # If it's a generic text click, support text selectors
                if not (sel.startswith("/") or sel.startswith(".") or sel.startswith("#") or "[" in sel):
                    # Try text matching
                    element = page.locator(f"text={sel}").first
                else:
                    element = page.locator(sel).first
                
                await element.click(timeout=10000)
                return f"Clicked element: '{sel}'"

            elif command == "type_element":
                sel = parameters["selector"]
                text = parameters["text"]
                if not (sel.startswith("/") or sel.startswith(".") or sel.startswith("#") or "[" in sel):
                    element = page.locator(f"text={sel}").first
                else:
                    element = page.locator(sel).first
                
                await element.fill(text, timeout=10000)
                return f"Typed text into element: '{sel}'"

            elif command == "scroll_browser":
                direction = parameters["direction"]
                amount = parameters.get("amount", 500)
                scroll_y = amount if direction == "down" else -amount
                await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                return f"Scrolled page {direction} by {amount} pixels."

            elif command == "read_page_content":
                # Extract clean text from page body using standard javascript
                text = await page.evaluate("() => document.body.innerText")
                # Basic cleanup
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                markdown_content = "\n".join(lines[:150])  # limit extraction height
                return f"Extracted Content:\n{markdown_content}"

            elif command == "switch_tab":
                tab_idx = parameters.get("tab_index")
                title_substring = parameters.get("title")
                
                if tab_idx is not None:
                    if 0 <= tab_idx < len(sdata["pages"]):
                        sdata["active_page_index"] = tab_idx
                        p = sdata["pages"][tab_idx]
                        await p.bring_to_front()
                        t = await p.title()
                        return f"Switched focus to tab #{tab_idx}: '{t}'"
                    else:
                        raise ValueError(f"Invalid tab index: {tab_idx}. Active count: {len(sdata['pages'])}")
                
                if title_substring:
                    for i, p in enumerate(sdata["pages"]):
                        t = await p.title()
                        if title_substring.lower() in t.lower():
                            sdata["active_page_index"] = i
                            await p.bring_to_front()
                            return f"Switched focus to matching tab #{i}: '{t}'"
                    raise ValueError(f"No tab title matched substring: '{title_substring}'")

                # If tab index/title are omitted, create a new tab page
                new_p = await sdata["context"].new_page()
                sdata["pages"].append(new_p)
                sdata["active_page_index"] = len(sdata["pages"]) - 1
                return f"Opened new browser tab #{sdata['active_page_index']}."

            elif command == "close_tab":
                idx = sdata["active_page_index"]
                if len(sdata["pages"]) <= 1:
                    await self.close_session(session_id)
                    return "Closed last active tab. Browser session closed."
                
                closed_p = sdata["pages"].pop(idx)
                await closed_p.close()
                sdata["active_page_index"] = max(0, idx - 1)
                new_p = sdata["pages"][sdata["active_page_index"]]
                await new_p.bring_to_front()
                t = await new_p.title()
                return f"Closed tab #{idx}. Active tab now #{sdata['active_page_index']}: '{t}'"

            elif command == "download_file":
                # Validate link url first
                url = parameters["url"]
                is_valid, dest_path = self.validate_file_path(os.path.basename(url))
                if not is_valid:
                    raise PermissionError(dest_path)
                
                # Perform Playwright download capture
                async with page.expect_download(timeout=15000) as download_info:
                    await page.goto(url)
                
                download = await download_info.value
                await download.save_as(dest_path)
                return f"File downloaded successfully to '{dest_path}'."

            elif command == "upload_file":
                sel = parameters["selector"]
                fp = parameters["file_path"]
                is_valid, abs_path = self.validate_file_path(fp)
                if not is_valid:
                    raise PermissionError(abs_path)

                if not os.path.exists(abs_path):
                    raise FileNotFoundError(f"File not found: '{abs_path}'")
                
                element = page.locator(sel).first
                await element.set_input_files(abs_path, timeout=10000)
                return f"Successfully uploaded file '{abs_path}' to element '{sel}'."

            return f"Error: Command '{command}' is not supported by the browser tool."
            
        except Exception as e:
            logger.error(f"Playwright error during {command}: {e}", exc_info=True)
            return f"Error executing browser action: {e}"

    async def get_current_url(self, session_id: str) -> str:
        try:
            page = await self.get_active_page(session_id)
            return page.url
        except Exception:
            return ""

    async def get_page_title(self, session_id: str) -> str:
        try:
            page = await self.get_active_page(session_id)
            return await page.title()
        except Exception:
            return ""

    async def execute_action(self, session_id: str, query: str) -> str:
        """
        Direct execution of a single browser command from text input.
        """
        self._prune_expired_confirmations()
        
        q_lower = query.lower().strip()

        # 1. Check if user is replying to a pending confirmation
        if session_id in self._pending_confirmations:
            pending = self._pending_confirmations[session_id]
            if q_lower in ["yes", "confirm", "go ahead", "y", "okay", "proceed", "sure"]:
                cmd = pending["command"]
                params = pending["parameters"]
                del self._pending_confirmations[session_id]
                return await self._run_browser_action(session_id, cmd, params)
            elif q_lower in ["no", "cancel", "stop", "n", "dont", "don't"]:
                del self._pending_confirmations[session_id]
                return "Action cancelled."
            else:
                return f"I have a pending action to execute: [{pending['command']}]. Please answer 'yes' to proceed, or 'no' to cancel."

        # 2. Parse query to command and parameters using LLM
        from tools.registry import get_tool_prompt
        from app.models.chat_models import ChatRequest
        from app.services.llm.base import GenerationConfig
        import re
        chat_req = ChatRequest(message=f"Request to parse: '{query}'")
        
        try:
            llm = self.llm
            if llm is None:
                from app.services.factory import ServiceFactory
                llm = ServiceFactory.get_llm()
            result = await llm.generate_response(
                request=chat_req,
                system_prompt=get_tool_prompt(),
                config=GenerationConfig(temperature=0.0)
            )
            resp_text = result.response.strip()
            if resp_text.startswith("```"):
                resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
                resp_text = re.sub(r"\n```$", "", resp_text)
            
            import json
            parsed = json.loads(resp_text)
            command = parsed.get("command")
            parameters = parsed.get("parameters", {})
        except Exception as parse_err:
            logger.warning(f"Failed parsing browser command via LLM: {parse_err}. Trying simple fallback routing.")
            command, parameters = self._fallback_regex_parse(query)
            if not command:
                return "I could not understand that browser command. Please rephrase."

        # 3. Check safety tier and execute
        return await self.execute_browser_command(session_id, command, parameters)

    def _fallback_regex_parse(self, query: str) -> Tuple[Optional[str], Dict[str, Any]]:
        q_lower = query.lower()
        if "open browser" in q_lower or "launch browser" in q_lower:
            return "open_browser", {}
        if "navigate to" in q_lower or "go to" in q_lower or "open url" in q_lower:
            words = q_lower.split()
            for w in words:
                if w.startswith("http://") or w.startswith("https://") or "www." in w:
                    url = w if w.startswith("http") else "https://" + w
                    return "navigate_url", {"url": url}
        if "scroll down" in q_lower:
            return "scroll_browser", {"direction": "down"}
        if "scroll up" in q_lower:
            return "scroll_browser", {"direction": "up"}
        if "read page" in q_lower or "extract page" in q_lower or "get page content" in q_lower:
            return "read_page_content", {}
        return None, {}
        
    def _prune_expired_confirmations(self):
        now = time.time()
        expired = [sid for sid, data in self._pending_confirmations.items() if now - data["timestamp"] > 120.0]
        for sid in expired:
            del self._pending_confirmations[sid]
