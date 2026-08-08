"""
ToolSelector validates tool invocation parameters against closed schemas.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging

from tools.registry import get_tool_schemas

logger = logging.getLogger("jarvis.agent.registry")

class ToolSelector:
    """
    Validates tool names and parameters against get_tool_schemas() definition from tools/registry.py.
    """
    def __init__(self):
        self.schemas = {s["name"]: s for s in get_tool_schemas()}

    def validate_tool_invocation(self, tool_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates tool execution parameters.
        Returns (is_valid, error_message).
        """
        schema = self.schemas.get(tool_name)
        if not schema:
            return False, f"Unknown tool: '{tool_name}' is not in the registered tool schema list."

        properties = schema.get("parameters", {}).get("properties", {})
        required = schema.get("parameters", {}).get("required", [])

        # 1. Check required parameters
        for req in required:
            if req not in parameters:
                return False, f"Missing required parameter '{req}' for tool '{tool_name}'."

        # 2. Check parameter types and boundaries
        for key, val in parameters.items():
            prop_def = properties.get(key)
            if not prop_def:
                return False, f"Unrecognized parameter '{key}' for tool '{tool_name}'."

            expected_type = prop_def.get("type")
            if expected_type == "integer" and not isinstance(val, int):
                # Try parsing if string
                if isinstance(val, str) and val.isdigit():
                    parameters[key] = int(val)
                else:
                    return False, f"Invalid type for parameter '{key}': expected integer, got {type(val).__name__}."
            elif expected_type == "string" and not isinstance(val, str):
                return False, f"Invalid type for parameter '{key}': expected string, got {type(val).__name__}."
            elif expected_type == "array" and not isinstance(val, list):
                return False, f"Invalid type for parameter '{key}': expected array/list, got {type(val).__name__}."

            # Enum checks (e.g. launch_app app_name whitelisting)
            if "enum" in prop_def and val not in prop_def["enum"]:
                return False, f"Invalid value '{val}' for parameter '{key}': must be one of {prop_def['enum']}."

        return True, None
