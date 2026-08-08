"""
OS-level desktop automation tool wrapper for PyAutoGUI, PyGetWindow, and subprocess.
"""
import os
import time
import ctypes
import subprocess
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.tools.desktop")

# Conditional imports to support headless/non-Windows environments gracefully
try:
    import pyautogui
    # Configure safety fail-safe corner to avoid lockouts (move mouse to top-left to abort)
    pyautogui.FAILSAFE = True
except ImportError:
    pyautogui = None
    logger.warning("pyautogui not found or cannot be imported in this environment.")

try:
    import pygetwindow as gw
except ImportError:
    gw = None
    logger.warning("pygetwindow not found or cannot be imported in this environment.")


class DesktopAutomationTool:
    """
    Handles physical OS interactions.
    All operations are synchronous and run on Windows.
    For non-Windows or headless environments, falls back to mock/dry-run log actions.
    """
    
    # App allowlist mapping
    APP_ALLOWLIST = {
        "notepad": "notepad.exe",
        "chrome": "chrome.exe",
        "vscode": "code",
        "explorer": "explorer.exe"
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def _is_gui_available(self) -> bool:
        return pyautogui is not None and not self.dry_run

    def get_screen_size(self) -> Dict[str, int]:
        if not self._is_gui_available():
            return {"width": 1920, "height": 1080}
        w, h = pyautogui.size()
        return {"width": w, "height": h}

    def take_screenshot(self, dest_path: str) -> str:
        """
        Takes a screenshot and saves it to dest_path. No vision analysis is done in Phase 6.
        """
        logger.info(f"Taking screenshot, saving to: {dest_path}")
        if not self._is_gui_available():
            return f"[Dry-Run] Saved mock screenshot to {dest_path}"
        
        # Ensure parent folder exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        screenshot = pyautogui.screenshot()
        screenshot.save(dest_path)
        return f"Screenshot saved successfully to {dest_path}"

    def move_mouse(self, x: int, y: int) -> str:
        if not self._is_gui_available():
            return f"[Dry-Run] Moved mouse to ({x}, {y})"
        
        # Validate coordinates are non-negative
        if x < 0 or y < 0:
            raise ValueError("Coordinates must be non-negative")
            
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Moved mouse to ({x}, {y})"

    def click_mouse(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        if not self._is_gui_available():
            return f"[Dry-Run] Clicked mouse {button} button {clicks} times at ({x}, {y})"
            
        if x < 0 or y < 0:
            raise ValueError("Coordinates must be non-negative")
            
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        return f"Clicked mouse {button} button at ({x}, {y})"

    def focus_window(self, title: str) -> str:
        """
        Attempts to find a window containing title and bring it to focus.
        """
        if gw is None or self.dry_run:
            return f"[Dry-Run] Focused window matching title: '{title}'"
            
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            raise ValueError(f"No window found matching title: '{title}'")
            
        target = windows[0]
        if target.isMinimized:
            target.restore()
        target.activate()
        return f"Focused window: '{target.title}'"

    def get_active_window_title(self) -> str:
        if gw is None or self.dry_run:
            return "[Dry-Run] Active Window"
        try:
            active = gw.getActiveWindow()
            return active.title if active else ""
        except Exception:
            return ""

    def type_text(self, text: str, target_window: Optional[str] = None) -> str:
        """
        Types text. If target_window is specified, focuses it first and waits.
        """
        focused_msg = ""
        if target_window:
            focused_msg = self.focus_window(target_window) + " | "
            time.sleep(0.2)  # focus verification sleep

        if not self._is_gui_available():
            return f"{focused_msg}[Dry-Run] Typed text: '{text}'"
            
        pyautogui.write(text, interval=0.01)
        return f"{focused_msg}Typed text: '{text}'"

    def press_key(self, key: str) -> str:
        if not self._is_gui_available():
            return f"[Dry-Run] Pressed key: '{key}'"
            
        pyautogui.press(key)
        return f"Pressed key: '{key}'"

    def hotkey(self, keys: List[str]) -> str:
        if not self._is_gui_available():
            return f"[Dry-Run] Executed hotkey combination: {keys}"
            
        pyautogui.hotkey(*keys)
        return f"Executed hotkey: {keys}"

    def list_windows(self) -> List[str]:
        if gw is None or self.dry_run:
            return ["[Dry-Run] Window A", "[Dry-Run] Window B"]
            
        return [w.title for w in gw.getAllWindows() if w.title.strip()]

    def close_window(self, title: str) -> str:
        if gw is None or self.dry_run:
            return f"[Dry-Run] Closed window matching: '{title}'"
            
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            raise ValueError(f"No window found matching title: '{title}'")
            
        windows[0].close()
        return f"Closed window matching: '{title}'"

    def minimize_window(self, title: str) -> str:
        if gw is None or self.dry_run:
            return f"[Dry-Run] Minimized window: '{title}'"
            
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            raise ValueError(f"No window found matching title: '{title}'")
            
        windows[0].minimize()
        return f"Minimized window matching: '{title}'"

    def maximize_window(self, title: str) -> str:
        if gw is None or self.dry_run:
            return f"[Dry-Run] Maximized window: '{title}'"
            
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            raise ValueError(f"No window found matching title: '{title}'")
            
        windows[0].maximize()
        return f"Maximized window matching: '{title}'"

    def launch_app(self, app_name: str, args: Optional[List[str]] = None) -> str:
        """
        Launches an application from the allowlist.
        Does not allow arbitrary paths, cmd.exe, or powershell.exe.
        """
        app_name_clean = app_name.lower().strip()
        if app_name_clean not in self.APP_ALLOWLIST:
            raise ValueError(f"Application '{app_name}' is not in the allowlist. Launching blocked.")
            
        executable = self.APP_ALLOWLIST[app_name_clean]
        
        # Build command array
        cmd_args = [executable]
        if args:
            cmd_args.extend(args)
            
        logger.info(f"Launching app from allowlist: {cmd_args}")
        if self.dry_run:
            return f"[Dry-Run] Launched application: {cmd_args}"
            
        # Spawn application process without blocking, avoiding shell=True
        subprocess.Popen(cmd_args, shell=False)
        return f"Launched application: '{app_name}' successfully."

    def set_volume(self, level: int) -> str:
        """
        Volume control using native volume keys via PyAutoGUI.
        Since level is relative, we log the command.
        """
        if not self._is_gui_available():
            return f"[Dry-Run] Set volume level to {level}%"
            
        # Simulates a media key volume toggle
        if level <= 0:
            pyautogui.press("volumemute")
            return "Volume muted."
        elif level > 50:
            pyautogui.press("volumeup", presses=5)
        else:
            pyautogui.press("volumedown", presses=5)
            
        return f"Volume adjusted relative to target: {level}%"

    def lock_screen(self) -> str:
        """
        Lock screen workstation command on Windows.
        """
        if self.dry_run:
            return "[Dry-Run] Screen locked successfully."
            
        # Native Windows user32 LockWorkStation call
        try:
            ctypes.windll.user32.LockWorkStation()
            return "Screen locked successfully."
        except Exception as e:
            # Fallback or stub if not on Windows
            logger.warning(f"Native lock failed or not supported in this OS environment: {e}")
            return f"Lock screen command issued, but not fully supported on this OS: {e}"

    def set_brightness(self, level: int) -> str:
        """
        Brightness control is explicitly marked as unsupported/stub in Phase 6.
        """
        logger.info(f"Attempted brightness set to {level}%. Unsupported.")
        return "Brightness control is currently unsupported on Windows in this phase configuration."

    def toggle_audio_device(self) -> str:
        """
        Audio output device toggle is explicitly marked as unsupported/stub in Phase 6.
        """
        logger.info("Attempted audio device toggle. Unsupported.")
        return "Audio output device toggle is currently unsupported on Windows in this phase configuration."
