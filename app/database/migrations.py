"""
Automatic table creation for local databases.
"""
import os
import logging
from app.database.base import Base
from app.database.session import engine
from app.config.settings import settings

logger = logging.getLogger("jarvis.database")

async def init_db() -> None:
    """
    Initializes the database by creating all tables if they do not exist.
    """
    try:
        # Resolve folder paths for SQLite db
        if settings.SQLITE_DB_PATH:
            db_dir = os.path.dirname(settings.SQLITE_DB_PATH)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                
        # Resolve folder paths for ChromaDB
        if settings.CHROMA_DB_PATH:
            if not os.path.exists(settings.CHROMA_DB_PATH):
                os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
                
        logger.info("Initializing database schemas...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
