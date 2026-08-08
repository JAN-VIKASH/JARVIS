"""
ReflectionEngine validates OS state changes and tool executions.
"""
from typing import Dict, Any, List
import logging

from tools.desktop_tool import DesktopAutomationTool

logger = logging.getLogger("jarvis.agent.reflection")

class ReflectionEngine:
    """
    Verifies state results of executed tools.
    """
    def __init__(self, desktop_tool: DesktopAutomationTool):
        self.desktop_tool = desktop_tool

    async def verify_step(self, tool_name: str, parameters: Dict[str, Any], tool_result: str) -> bool:
        """
        Runs state verification checks depending on the tool executed.
        Returns True if expected state change is verified, else False.
        """
        # If execution returned an error message, it is an automatic failure
        if "error" in tool_result.lower() or "exception" in tool_result.lower() or "failed" in tool_result.lower():
            return False

        if tool_name == "launch_app":
            app_name = parameters.get("app_name", "").lower().strip()
            # Try to list windows and verify if the window is open
            try:
                # Under async thread to prevent blocking
                import asyncio
                window_titles = await asyncio.to_thread(self.desktop_tool.list_windows)
                
                # Check if any window title contains the app name
                # Notepad -> "Notepad", VS Code -> "Visual Studio Code" or "code", etc.
                keyword = app_name
                if app_name == "vscode":
                    keyword = "code"
                elif app_name == "chrome":
                    keyword = "google chrome"
                    
                match = any(keyword in t.lower() for t in window_titles)
                if not match and self.desktop_tool.dry_run:
                    # In dry run mode, always pass
                    return True
                return match
            except Exception as e:
                logger.warning(f"Reflection verification failed for launch_app: {e}")
                return False

        if tool_name == "focus_window":
            title = parameters.get("title", "").lower().strip()
            try:
                import asyncio
                active_title = await asyncio.to_thread(self.desktop_tool.get_active_window_title)
                if not active_title and self.desktop_tool.dry_run:
                    return True
                return title in active_title.lower()
            except Exception:
                return False

        # For general tools, if no exceptions occurred, default to success
        return True
