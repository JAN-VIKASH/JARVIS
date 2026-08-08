"""
Closed schema definitions for JARVIS desktop automation tools.
Defines allowed commands, parameters, and instructions for LLM parsing.
"""
from typing import List, Dict, Any

# Closed command definitions with parameters and validation criteria
DESKTOP_TOOL_SCHEMAS = [
    {
        "name": "move_mouse",
        "description": "Moves the mouse pointer to the specified x, y screen coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate on screen (must be non-negative)."},
                "y": {"type": "integer", "description": "Y coordinate on screen (must be non-negative)."}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "click_mouse",
        "description": "Clicks the mouse pointer at the specified coordinate. Windows focus is handled automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate on screen (must be non-negative)."},
                "y": {"type": "integer", "description": "Y coordinate on screen (must be non-negative)."},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "Number of times to click."}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "type_text",
        "description": "Types the specified text on the active keyboard focus. Focuses target_window first if provided.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The exact string characters to write/type."},
                "target_window": {"type": "string", "description": "Window title to activate first."}
            },
            "required": ["text"]
        }
    },
    {
        "name": "press_key",
        "description": "Simulates pressing a single keyboard key (e.g. enter, space, tab, backspace).",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key identifier string."}
            },
            "required": ["key"]
        }
    },
    {
        "name": "hotkey",
        "description": "Presses a combination of hotkeys simultaneously (e.g. ['alt', 'f4'] to close windows).",
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of key strings to hold down simultaneously."
                }
            },
            "required": ["keys"]
        }
    },
    {
        "name": "list_windows",
        "description": "Returns a list of titles of all currently open GUI windows.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "focus_window",
        "description": "Brings the specified window matching target title to the active foreground.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title (or substring) of the target window."}
            },
            "required": ["title"]
        }
    },
    {
        "name": "close_window",
        "description": "Closes the window matching the target title.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title (or substring) of the window to close."}
            },
            "required": ["title"]
        }
    },
    {
        "name": "launch_app",
        "description": "Launches a local application from the allowlist. Arbitrary programs are blocked.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "enum": ["notepad", "chrome", "vscode", "explorer"]},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of launch arguments."
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "set_volume",
        "description": "Sets system audio volume level relative to target %.",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Target volume (0 for mute, 100 for max)."}
            },
            "required": ["level"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Takes a screenshot of the display screen. Saves PNG to folder.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "lock_screen",
        "description": "Locks the current workstation screen.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "set_brightness",
        "description": "Stubs setting monitor brightness. Unsupported in this phase.",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {"type": "integer"}
            },
            "required": ["level"]
        }
    },
    {
        "name": "toggle_audio_device",
        "description": "Stubs switching sound hardware output devices. Unsupported in this phase.",
        "parameters": {"type": "object", "properties": {}}
    }
]


BROWSER_TOOL_SCHEMAS = [
    {
        "name": "open_browser",
        "description": "Opens a new browser session or tab.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "navigate_url",
        "description": "Navigates the browser to the specified URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The target website URL (must start with http:// or https://)."}
            },
            "required": ["url"]
        }
    },
    {
        "name": "click_element",
        "description": "Clicks an element on the active page matching the CSS selector or text description.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or text content to click."}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "type_element",
        "description": "Types text into a form or input field matching the selector.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or field label/description."},
                "text": {"type": "string", "description": "Text string characters to type."}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "scroll_browser",
        "description": "Scrolls the current page up or down.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "amount": {"type": "integer", "description": "Amount in pixels to scroll (optional)."}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "read_page_content",
        "description": "Extracts the markdown formatted text content of the active page.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "switch_tab",
        "description": "Switches focus to another tab by its index or title substring.",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_index": {"type": "integer", "description": "Zero-based tab index (optional)."},
                "title": {"type": "string", "description": "Substring of page title to match (optional)."}
            }
        }
    },
    {
        "name": "close_tab",
        "description": "Closes the current active browser tab.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "download_file",
        "description": "Downloads a file from a URL to the configured downloads folder.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Direct download link URL."}
            },
            "required": ["url"]
        }
    },
    {
        "name": "upload_file",
        "description": "Uploads a local file to the selected upload input element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "Selector for the file upload input element."},
                "file_path": {"type": "string", "description": "Path to the local file to upload."}
            },
            "required": ["selector", "file_path"]
        }
    }
]

VISION_TOOL_SCHEMAS = [
    {
        "name": "take_screenshot",
        "description": "Captures a screenshot of the main monitor screen and saves it temporarily.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "read_screen",
        "description": "Performs local OCR on the screen screenshot to extract all text strings and bounding boxes.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "find_screen_element",
        "description": "Locates elements matching target text on the screen and returns their pixel coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to search for on screen."}
            },
            "required": ["text"]
        }
    },
    {
        "name": "describe_screen",
        "description": "Describes visual content or answers screen queries using optional VLM context.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Question or instruction about the screen visual state."}
            },
            "required": ["prompt"]
        }
    }
]


def get_tool_schemas() -> List[Dict[str, Any]]:
    return DESKTOP_TOOL_SCHEMAS + BROWSER_TOOL_SCHEMAS + VISION_TOOL_SCHEMAS


def get_tool_prompt() -> str:
    """
    Constructs the prompt instruct guiding LLM parameter parsing.
    """
    schemas_str = ""
    for s in get_tool_schemas():
        schemas_str += f"- Command: '{s['name']}'\n  Description: {s['description']}\n  Parameters: {s['parameters']}\n\n"
        
    return (
        "You are the JARVIS Command Parser.\n"
        "Your task is to parse the user's action request into a JSON structure specifying the command and parameters.\n"
        "You must output ONLY a valid JSON object matching the schema. Do not output markdown, notes, or explanations outside the JSON.\n\n"
        "Available Schemas:\n"
        f"{schemas_str}"
        "Format Output EXACTLY like this:\n"
        "{\n"
        '  "command": "command_name_here",\n'
        '  "parameters": {\n'
        '    "param_name": "param_value"\n'
        '  }\n'
        "}\n\n"
        "Rules:\n"
        "1. Map to 'launch_app' only for notepad, chrome, vscode, explorer. Reject others.\n"
        "2. Keep the command and key names matching the schemas exactly.\n"
        "3. Output ONLY the raw JSON block without formatting wrappers like ```json."
    )
