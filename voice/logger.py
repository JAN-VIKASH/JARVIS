"""
Logger setup for the voice interface.
"""
import logging
import sys

# Format specific to voice events
log_format = "[%(asctime)s] %(levelname)-8s in %(module)s: %(message)s"

voice_logger = logging.getLogger("jarvis.voice")
voice_logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if already configured
if not voice_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    voice_logger.addHandler(handler)
