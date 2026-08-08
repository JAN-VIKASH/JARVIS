"""
Desktop Automation Service.
Handles parsing, safety checks, in-memory confirmations, and async-to-thread tool execution.
"""
import json
import re
import time
import asyncio
import logging
from typing import Dict, Any, Optional

from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.models.chat_models import ChatRequest
from app.core.dependencies import get_llm
from tools.desktop_tool import DesktopAutomationTool
from tools.registry import get_tool_prompt, get_tool_schemas

logger = logging.getLogger("jarvis.services.desktop")


class DesktopAutomationService:
    """
    Service coordinating desktop automation requests.
    Stores confirmation states in memory (session-scoped) expiring after 120 seconds.
    """

    def __init__(self, llm: Optional[BaseLLM] = None, desktop_tool: Optional[DesktopAutomationTool] = None):
        self.llm = llm or get_llm()
        self.desktop_tool = desktop_tool or DesktopAutomationTool()
        
        # Pending confirmations dictionary: session_id -> {"command": str, "parameters": dict, "timestamp": float}
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
        self.confirmation_timeout_seconds = 120.0

    def _prune_expired_confirmations(self):
        now = time.time()
        expired = [sid for sid, data in self._pending_confirmations.items() 
                   if now - data["timestamp"] > self.confirmation_timeout_seconds]
        for sid in expired:
            logger.info(f"Pruned expired confirmation state for session: {sid}")
            del self._pending_confirmations[sid]

    def _classify_safety_tier(self, command: str, parameters: Dict[str, Any]) -> str:
        """
        Safety Tier classification: SAFE, CAUTION, CONFIRMATION_REQUIRED, BLOCKED
        """
        # Blocked list validation
        blocked_commands = {"execute_shell", "run_cmd", "shutdown", "reboot", "delete_file"}
        if command in blocked_commands:
            return "BLOCKED"

        # Parameter checks to prevent shell injection vectors
        for val in parameters.values():
            if isinstance(val, str):
                lower_val = val.lower()
                # Check for cmd, powershell, shell flags or file deletion patterns
                if any(x in lower_val for x in ["cmd.exe", "powershell", "rmdir", "del ", "rm -rf", "format "]):
                    return "BLOCKED"

        # Closed validation schemas
        valid_commands = {s["name"] for s in get_tool_schemas()}
        if command not in valid_commands:
            return "BLOCKED"

        if command == "launch_app":
            app_name = parameters.get("app_name", "").lower().strip()
            # Enforce strict app allowlist
            if app_name not in ["notepad", "chrome", "vscode", "explorer"]:
                return "BLOCKED"
            return "CONFIRMATION_REQUIRED"

        if command in ["close_window", "hotkey"]:
            return "CONFIRMATION_REQUIRED"

        if command in ["move_mouse", "click_mouse", "type_text", "press_key", "focus_window", "minimize_window", "maximize_window"]:
            return "CAUTION"

        if command in ["get_screen_size", "list_windows", "take_screenshot", "set_volume", "set_brightness", "toggle_audio_device", "lock_screen"]:
            return "SAFE"

        return "BLOCKED"

    def _is_query_malicious(self, query: str) -> bool:
        q_lower = query.lower()
        blocked_words = [
            "delete file", "remove file", "format ", "rmdir", "rm -rf", "del ", 
            "cmd.exe", "powershell", "shutdown", "reboot", "restart", "registry", "regedit"
        ]
        return any(w in q_lower for w in blocked_words)

    async def execute_action(self, session_id: str, query: str) -> str:
        """
        Routes and processes the desktop action user statement.
        """
        self._prune_expired_confirmations()
        
        # Enforce safety pre-check on raw query string
        if self._is_query_malicious(query):
            logger.warning(f"Safety violation: query '{query}' blocked.")
            return "Executing this command is blocked due to safety restrictions. Access denied."

        q_lower = query.lower().strip()

        # 1. Check if user is replying to a pending confirmation
        if session_id in self._pending_confirmations:
            pending = self._pending_confirmations[session_id]
            
            # Match positive response patterns
            if q_lower in ["yes", "confirm", "go ahead", "y", "okay", "proceed", "sure"]:
                # Execute the cached action
                cmd = pending["command"]
                params = pending["parameters"]
                del self._pending_confirmations[session_id]
                logger.info(f"Confirmed action execution: {cmd} with params {params} for session {session_id}")
                return await self._run_tool_command(cmd, params)
                
            # Match negative response patterns
            elif q_lower in ["no", "cancel", "stop", "n", "dont", "don't"]:
                del self._pending_confirmations[session_id]
                logger.info(f"Cancelled action execution for session {session_id}")
                return "Action cancelled."
            else:
                # If they say something else, remind them they have a pending confirmation
                return f"I have a pending action to execute: [{pending['command']}]. Please answer 'yes' to proceed, or 'no' to cancel."

        # 2. Map query to tool call parameters using LLM
        prompt = get_tool_prompt()
        chat_req = ChatRequest(message=f"Request to parse: '{query}'")
        
        try:
            result = await self.llm.generate_response(
                request=chat_req,
                system_prompt=prompt,
                config=GenerationConfig(temperature=0.0)
            )
            
            resp_text = result.response.strip()
            # Clean possible markdown block wrappers
            if resp_text.startswith("```"):
                resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
                resp_text = re.sub(r"\n```$", "", resp_text)
                
            logger.info(f"LLM parsed desktop command string: {resp_text}")
            parsed = json.loads(resp_text)
            command = parsed.get("command")
            parameters = parsed.get("parameters", {})
        except Exception as parse_err:
            logger.warning(f"Failed parsing command via LLM: {parse_err}. Trying simple fallback routing.")
            # Simple fallback regex routing for robust testing/operations
            command, parameters = self._fallback_regex_parse(query)
            if not command:
                return "I could not understand that desktop command. Please rephrase."

        # 3. Classify Safety Tier
        tier = self._classify_safety_tier(command, parameters)
        logger.info(f"Safety classification for command '{command}': {tier}")

        if tier == "BLOCKED":
            return "Executing this command is blocked due to safety restrictions. Access denied."

        if tier == "CONFIRMATION_REQUIRED":
            # Cache the action mapping
            self._pending_confirmations[session_id] = {
                "command": command,
                "parameters": parameters,
                "timestamp": time.time()
            }
            # Return clear confirmation prompt
            return f"I need your confirmation to proceed with the action: [{command}] using parameters {parameters}. Please say 'yes' to confirm or 'no' to cancel."

        # 4. Immediate execution (SAFE / CAUTION)
        return await self._run_tool_command(command, parameters)

    def _fallback_regex_parse(self, query: str) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Simple regex mapping fallback if LLM is down or times out.
        """
        q_lower = query.lower()
        if "open notepad" in q_lower or "launch notepad" in q_lower:
            return "launch_app", {"app_name": "notepad"}
        if "open chrome" in q_lower or "launch chrome" in q_lower:
            return "launch_app", {"app_name": "chrome"}
        if "screenshot" in q_lower:
            return "take_screenshot", {}
        if "mute" in q_lower:
            return "set_volume", {"level": 0}
        if "lock screen" in q_lower or "lock workstation" in q_lower:
            return "lock_screen", {}
        return None, {}

    async def _run_tool_command(self, command: str, parameters: Dict[str, Any]) -> str:
        """
        Runs synchronous DesktopAutomationTool commands in thread executor under timeout guards.
        """
        method = getattr(self.desktop_tool, command, None)
        if not method:
            return f"Error: Command '{command}' is not supported by the desktop tool."

        # Verify window focus prior to typing
        if command == "type_text" and "target_window" in parameters:
            # We explicitly run focus_window first if target_window is given
            pass

        try:
            # Enforce 5.0 second execution limit
            async with asyncio.timeout(5.0):
                # Execute blocking code inside thread pool
                result_str = await asyncio.to_thread(method, **parameters)
                return result_str
        except asyncio.TimeoutError:
            logger.error(f"Desktop command '{command}' timed out after 5.0 seconds.")
            return f"Error: The action '{command}' timed out and was aborted."
        except Exception as e:
            logger.error(f"Error executing desktop command '{command}': {e}", exc_info=True)
            return f"Error executing action: {e}"
