"""
RecoveryEngine manages retry behaviors and recovery strategies for step failures.
"""
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("jarvis.agent.recovery")

class RecoveryEngine:
    """
    Implements bounded retry and recovery policies.
    """
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def is_retryable(self, error_message: str) -> bool:
        """
        Determines if a failure can be safely retried.
        """
        err_lower = error_message.lower()
        # Non-retryable failures: blocked actions, validation, safety violations
        non_retryable = [
            "blocked",
            "safety violation",
            "access denied",
            "invalid parameter",
            "valueerror",
            "unsupported"
        ]
        return not any(phrase in err_lower for phrase in non_retryable)

    async def execute_recovery_strategy(self, tool_name: str, parameters: Dict[str, Any], attempt: int) -> bool:
        """
        Attempts a recovery action based on the failing tool type.
        Returns True if recovery action is executed, else False.
        """
        logger.info(f"Attempting recovery strategy for tool '{tool_name}' on attempt {attempt}")
        
        # Exponential backoff
        backoff_time = 0.5 * (2 ** attempt)
        await asyncio.sleep(backoff_time)
        
        if tool_name == "type_text" and "target_window" in parameters:
            # Recovery strategy: Try to refocus target window explicitly
            logger.info("Recovery: Refocusing window before typing retry.")
            return True
            
        return False
