"""
MemoryConflictResolver to intelligently resolve state conflicts.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from memory.sqlite_repository import SQLiteMemoryRepository

logger = logging.getLogger("jarvis.memory")

class MemoryConflictResolver:
    """
    Intelligently resolves conflicts between new memory inputs and existing stored facts/preferences.
    Supports version deactivation (optimistic locking) and multi-value relational merges.
    """
    def __init__(self, sqlite_repo: SQLiteMemoryRepository, chroma_repo=None):
        self.sqlite_repo = sqlite_repo
        self.chroma_repo = chroma_repo

    def _is_single_value(self, category: str, key: str) -> bool:
        """
        Determines if a given memory entity key represents a single-value attribute.
        """
        cat_lower = category.lower().strip()
        key_lower = key.lower().strip()
        
        # Identity or explicit single-value keys
        if cat_lower == "identity" or key_lower in {
            "name", "age", "location", "occupation", "birthday", 
            "favourite_language", "favorite_language"
        }:
            return True
            
        if key_lower.startswith("favorite_") or key_lower.startswith("favourite_"):
            return True
            
        return False

    async def resolve_and_save(self, m_type: str, category: str, key: str, value: str, confidence: float, score: int, session_id: str = "default") -> Dict[str, Any]:
        """
        Applies version checking, optimistic locking, and list-row splits to save a fact/preference.
        """
        if m_type not in ("fact", "preference"):
            # Goals/Notes/Tasks do not use key-based version resolution here, save directly
            if m_type == "goal":
                return await self.sqlite_repo.save_goal(title=key, description=value, status="active", importance=score)
            elif m_type == "note":
                return await self.sqlite_repo.save_note(title=key, content=value, importance=score)
            elif m_type == "task":
                return await self.sqlite_repo.save_task(session_id=session_id, title=key, description=value, status="pending", importance=score)
            return {}

        is_single = self._is_single_value(category, key)
        max_retries = 3

        for attempt in range(max_retries):
            # 1. Fetch current active record
            if m_type == "fact":
                active = await self.sqlite_repo.get_active_fact(category, key)
            else:
                active = await self.sqlite_repo.get_active_preference(category, key)

            if not active:
                # No existing record: simply insert as active version 1
                if m_type == "fact":
                    return await self._insert_new_version("user_facts", category, key, value, confidence, score, version=1)
                else:
                    return await self._insert_new_preference("preferences", category, key, value, confidence, score, version=1)

            # Active record exists. Let's compare values
            existing_value = active["value"]
            if existing_value == value:
                # Same value: update access metrics and return
                table_name = "user_facts" if m_type == "fact" else "preferences"
                await self.sqlite_repo.update_access_metrics(table_name, active["id"])
                active["access_count"] = (active.get("access_count") or 0) + 1
                return active

            # Different value! Apply rules
            if is_single:
                # Single-value: optimistic lock deactivation of old record, insert new active version
                table_name = "user_facts" if m_type == "fact" else "preferences"
                success = await self.sqlite_repo.deactivate_record(table_name, active["id"], active["version"])
                if not success:
                    # Concurrency conflict! Stale write detected, loop to refresh and retry
                    logger.warning(f"Optimistic lock check failed for {table_name} id={active['id']}, version={active['version']}. Retrying resolving...")
                    continue
                
                # Delete old vector from ChromaDB to prevent retrieval pollution
                if self.chroma_repo:
                    old_chroma_id = f"{m_type}_{active['id']}_{key}"
                    try:
                        self.chroma_repo.delete_embedding(old_chroma_id)
                    except Exception as e:
                        logger.error(f"Failed to delete old ChromaDB vector {old_chroma_id}: {e}")
                
                # Deactivation successful! Create next version
                next_version = active["version"] + 1
                if m_type == "fact":
                    return await self._insert_new_version("user_facts", category, key, value, confidence, score, version=next_version)
                else:
                    return await self._insert_new_preference("preferences", category, key, value, confidence, score, version=next_version)
            else:
                # Multi-value: insert new active row with version=1 directly. 
                # Note: duplicate values are avoided by identical check above, so this value is distinct.
                if m_type == "fact":
                    return await self._insert_new_version("user_facts", category, key, value, confidence, score, version=1)
                else:
                    return await self._insert_new_preference("preferences", category, key, value, confidence, score, version=1)

        raise RuntimeError(f"Failed to resolve concurrency conflict for memory after {max_retries} attempts.")

    async def _insert_new_version(
        self, table_name: str, category: str, key: str, value: str, confidence: float, importance: int, version: int
    ) -> Dict[str, Any]:
        """Helper to force-save a new fact version."""
        from app.database.session import get_async_session
        from app.database.models import UserFactModel
        async with get_async_session() as session:
            model = UserFactModel(
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                importance=importance,
                version=version,
                is_active=True
            )
            session.add(model)
            await session.flush()
            return {
                "id": model.id,
                "category": model.category,
                "key": model.key,
                "value": model.value,
                "confidence": model.confidence,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }

    async def _insert_new_preference(
        self, table_name: str, category: str, key: str, value: str, confidence: float, importance: int, version: int
    ) -> Dict[str, Any]:
        """Helper to force-save a new preference version."""
        from app.database.session import get_async_session
        from app.database.models import PreferenceModel
        async with get_async_session() as session:
            model = PreferenceModel(
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                importance=importance,
                version=version,
                is_active=True
            )
            session.add(model)
            await session.flush()
            return {
                "id": model.id,
                "category": model.category,
                "key": model.key,
                "value": model.value,
                "confidence": model.confidence,
                "importance": model.importance,
                "version": model.version,
                "is_active": model.is_active
            }
