"""
Prompts configuration and utilities.
"""

import os
from typing import Optional
from app.config.settings import settings
from app.utils.file_loader import load_file_content
from app.core.exceptions import ConfigurationError

class PromptConfig:
    """
    Manages loading and parsing system prompts.
    """
    def __init__(self):
        self._system_prompt: Optional[str] = None

    def get_system_prompt(self) -> str:
        """
        Retrieve the system prompt. Loads it from file if not cached.
        """
        if self._system_prompt is not None:
            return self._system_prompt
            
        prompt_path = settings.SYSTEM_PROMPT_PATH
        if not os.path.exists(prompt_path):
            raise ConfigurationError(f"System prompt file not found at path: {prompt_path}")
            
        try:
            self._system_prompt = load_file_content(prompt_path)
            return self._system_prompt
        except Exception as e:
            raise ConfigurationError(f"Failed to load system prompt: {e}")

# Global instance
prompt_config = PromptConfig()
