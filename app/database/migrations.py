"""
Automatic table creation for local databases with schema upgrades.
"""
import os
import logging
from sqlalchemy import text
from app.database.base import Base
from app.database.session import engine
from app.config.settings import settings

logger = logging.getLogger("jarvis.database")

async def upgrade_database_schema(conn) -> None:
    """
    Performs safe incremental schema alterations.
    Runs asynchronously using the active engine connection context.
    """
    try:
        # 1. Check/Add columns to 'tasks' table
        tasks_info = await conn.execute(text("PRAGMA table_info(tasks)"))
        existing_tasks_cols = {row[1] for row in tasks_info.fetchall()}
        
        if existing_tasks_cols and "session_id" not in existing_tasks_cols:
            logger.info("Migration: Adding session_id column to tasks table.")
            # SQLite does not allow NOT NULL without a default. Setting default value 'default'.
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN session_id VARCHAR(100) DEFAULT 'default' NOT NULL"))
            # Create index for the new column
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_session_id ON tasks (session_id)"))
            
        # 2. Check/Add columns to 'event_memories' table
        events_info = await conn.execute(text("PRAGMA table_info(event_memories)"))
        existing_events_cols = {row[1] for row in events_info.fetchall()}
        
        if existing_events_cols:
            recurrence_cols = [
                ("recurrence_rule", "VARCHAR(50)"),
                ("recurrence_until", "DATETIME"),
                ("recurrence_series_id", "VARCHAR(36)"),
                ("timezone", "VARCHAR(50)")
            ]
            
            for col_name, col_def in recurrence_cols:
                if col_name not in existing_events_cols:
                    logger.info(f"Migration: Adding {col_name} column to event_memories table.")
                    await conn.execute(text(f"ALTER TABLE event_memories ADD COLUMN {col_name} {col_def}"))
    except Exception as e:
        logger.error(f"Failed to perform schema upgrade: {e}", exc_info=True)

async def init_db() -> None:
    """
    Initializes the database by upgrading schemas and creating any missing tables.
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
            # Check existing tables to see if we should run schema upgrades first
            tables_result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            existing_tables = {row[0] for row in tables_result.fetchall()}
            
            if "tasks" in existing_tables or "event_memories" in existing_tables:
                await upgrade_database_schema(conn)
                
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
