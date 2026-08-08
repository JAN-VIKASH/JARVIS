"""
Application wide constants.
"""

from typing import Final

# Versioning and Metadata
APP_VERSION: Final[str] = "1.0.0"

# LLM Providers
PROVIDER_PLACEHOLDER: Final[str] = "placeholder"
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_CLAUDE: Final[str] = "claude"
PROVIDER_GEMINI: Final[str] = "gemini"

# System prompt filename
DEFAULT_SYSTEM_PROMPT_FILE: Final[str] = "system_prompt.txt"
