"""
Helper utilities for the JARVIS application.
"""

import time
from typing import Any, Dict

def get_current_timestamp() -> float:
    """
    Get current epoch timestamp in seconds.
    """
    return time.time()


def format_iso_timestamp(timestamp: float) -> str:
    """
    Format epoch timestamp into ISO 8601 string.
    """
    import datetime
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).isoformat()
