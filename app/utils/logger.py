"""
Logger utility module.
"""

import logging

def get_logger(name: str = "jarvis") -> logging.Logger:
    """
    Retrieve or create a logger with the given name.
    """
    return logging.getLogger(name)
