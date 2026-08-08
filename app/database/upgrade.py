import os
import sqlite3
import logging
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis.upgrade")

def upgrade_db() -> None:
    db_path = settings.SQLITE_DB_PATH
    if not os.path.exists(db_path):
        logger.info(f"No existing database found at {db_path}. Migration skipped.")
        return
        
    logger.info(f"Upgrading database schema at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Drop unique indexes if they exist
    indexes_to_drop = [
        "ix_user_facts_key",
        "ix_preferences_key",
        "ix_goals_title",
        "ix_tasks_title",
        "ix_notes_title"
    ]
    for idx in indexes_to_drop:
        try:
            cursor.execute(f"DROP INDEX IF EXISTS {idx}")
            logger.info(f"Dropped index {idx}")
        except Exception as e:
            logger.warning(f"Could not drop index {idx}: {e}")
            
    # 2. Add columns to entity tables
    tables = ["user_facts", "preferences", "goals", "tasks", "notes"]
    columns_to_add = [
        ("last_accessed_at", "DATETIME DEFAULT '2026-08-07 00:00:00'"),
        ("access_count", "INTEGER DEFAULT 0"),
        ("is_archived", "BOOLEAN DEFAULT 0"),
        ("is_active", "BOOLEAN DEFAULT 1"),
        ("version", "INTEGER DEFAULT 1"),
        ("is_deleted", "BOOLEAN DEFAULT 0"),
        ("deleted_at", "DATETIME")
    ]
    
    for table in tables:
        # Check existing columns to avoid adding them twice
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        for col_name, col_def in columns_to_add:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column {col_name} to table {table}")
                except Exception as e:
                    logger.error(f"Failed to add column {col_name} to {table}: {e}")
                    
    # 3. Add columns to memory_metadata table
    cursor.execute("PRAGMA table_info(memory_metadata)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    metadata_cols = [
        ("embedding_model", "VARCHAR(100)"),
        ("pending_index", "BOOLEAN DEFAULT 0"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("last_retry_at", "DATETIME"),
        ("status", "VARCHAR(20) DEFAULT 'active'")
    ]
    for col_name, col_def in metadata_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE memory_metadata ADD COLUMN {col_name} {col_def}")
                logger.info(f"Added column {col_name} to table memory_metadata")
            except Exception as e:
                logger.error(f"Failed to add column {col_name} to memory_metadata: {e}")
                
    # 4. Recreate non-unique indexes
    indexes_to_create = [
        ("ix_user_facts_key", "user_facts", "key"),
        ("ix_preferences_key", "preferences", "key"),
        ("ix_goals_title", "goals", "title"),
        ("ix_tasks_title", "tasks", "title"),
        ("ix_notes_title", "notes", "title")
    ]
    for idx_name, table_name, col_name in indexes_to_create:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({col_name})")
            logger.info(f"Created index {idx_name} on {table_name} ({col_name})")
        except Exception as e:
            logger.error(f"Failed to create index {idx_name}: {e}")
            
    conn.commit()
    conn.close()
    logger.info("Database schema upgrade complete.")

if __name__ == "__main__":
    upgrade_db()
