"""
Logging setup and configuration.
"""

import sys
import logging
from app.config.settings import settings


def configure_logging() -> None:
    """
    Configure the root logger and specific app logger.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Standard format for logs
    log_format = (
        "[%(asctime)s] %(levelname)-8s in %(module)s: %(message)s"
    )
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configure specific jarvis logger
    jarvis_logger = logging.getLogger("jarvis")
    jarvis_logger.setLevel(log_level)
    jarvis_logger.info(f"Logging initialized with level: {settings.LOG_LEVEL}")
