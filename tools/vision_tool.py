"""
Wrapper schemas and metadata descriptors for JARVIS local vision tools.
These tools are executed by the Agent ExecutionEngine via the VisionService.
"""
from typing import Dict, Any

# Minimum required tool definitions
VISION_TOOLS_METADATA = {
    "take_screenshot": {
        "description": "Captures a screenshot of the main monitor screen and saves it temporarily."
    },
    "read_screen": {
        "description": "Performs local OCR on the screen screenshot to extract all text strings and bounding boxes."
    },
    "find_screen_element": {
        "description": "Locates elements matching target text on the screen and returns their pixel coordinates."
    },
    "describe_screen": {
        "description": "Describes visual content or answers screen queries using optional VLM context."
    }
}
