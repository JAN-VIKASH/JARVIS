"""
MemoryDecayService manages memory lifecycle aging/archiving and background index retries.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from app.config.settings import settings
from app.database.session import get_async_session
from app.database.models import (
    UserFactModel,
    PreferenceModel,
    GoalModel,
    TaskModel,
    NoteModel,
    MemoryMetadataModel
)
from memory.sqlite_repository import SQLiteMemoryRepository
from memory.chroma_repository import ChromaMemoryRepository
from memory.embedding import EmbeddingService

logger = logging.getLogger("jarvis.memory")

class MemoryDecayService:
    """
    Manages the lifecycle of memories: soft archiving inactive records based on importance,
    and retrying pending ChromaDB vector indexing asynchronously in the background.
    """
    def __init__(
        self,
        sqlite_repo: SQLiteMemoryRepository,
        chroma_repo: ChromaMemoryRepository,
        embedding_service: EmbeddingService
    ):
        self.sqlite_repo = sqlite_repo
        self.chroma_repo = chroma_repo
        self.embedding_service = embedding_service
        self._loop_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self, interval_seconds: int = 60) -> None:
        """
        Starts the background processing loop. Idempotent.
        """
        if self._loop_task is not None and not self._loop_task.done():
            return
            
        self._running = True
        self._loop_task = asyncio.create_task(self._background_loop(interval_seconds))
        logger.info("MemoryDecayService background daemon started.")

    async def stop(self) -> None:
        """
        Gracefully shuts down the background daemon. Idempotent.
        """
        if self._loop_task is None:
            return
            
        logger.info("Stopping MemoryDecayService background daemon...")
        self._running = False
        task = self._loop_task
        self._loop_task = None
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("MemoryDecayService background daemon stopped.")

    async def _background_loop(self, interval: int) -> None:
        """
        Background execution loop executing decay and indexing retries.
        """
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self.decay_memories()
                await self.retry_pending_indexes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in MemoryDecayService background loop: {e}", exc_info=True)

    async def decay_memories(self) -> None:
        """
        Scans SQLite memory records and archives them if they exceed the inactivity thresholds.
        """
        try:
            low_cutoff = datetime.utcnow() - timedelta(days=settings.DECAY_LOW_THRESHOLD_DAYS)
            med_cutoff = datetime.utcnow() - timedelta(days=settings.DECAY_MEDIUM_THRESHOLD_DAYS)
            
            async with get_async_session() as session:
                for model_class in [UserFactModel, PreferenceModel, GoalModel, TaskModel, NoteModel]:
                    # 1. Decay Low Importance (< 40)
                    stmt_low = select(model_class).where(
                        model_class.is_archived == False,
                        model_class.is_deleted == False,
                        model_class.importance < 40,
                        model_class.last_accessed_at < low_cutoff
                    )
                    res_low = await session.execute(stmt_low)
                    for item in res_low.scalars().all():
                        item.is_archived = True
                        item.updated_at = datetime.utcnow()
                        logger.info(f"Lifecycle Decay: Archived low-importance record {item.id} of table {model_class.__tablename__}")
                        
                    # 2. Decay Medium Importance (40 <= importance < 80)
                    stmt_med = select(model_class).where(
                        model_class.is_archived == False,
                        model_class.is_deleted == False,
                        model_class.importance >= 40,
                        model_class.importance < 80,
                        model_class.last_accessed_at < med_cutoff
                    )
                    res_med = await session.execute(stmt_med)
                    for item in res_med.scalars().all():
                        item.is_archived = True
                        item.updated_at = datetime.utcnow()
                        logger.info(f"Lifecycle Decay: Archived medium-importance record {item.id} of table {model_class.__tablename__}")
                        
                await session.flush()
        except Exception as e:
            logger.error(f"Failed to decay memories: {e}", exc_info=True)

    async def retry_pending_indexes(self) -> None:
        """
        Fetches and retries vector indexing for records flagged as pending_index.
        """
        try:
            pending_list = await self.sqlite_repo.get_pending_indexes()
            if not pending_list:
                return
                
            now = datetime.utcnow()
            async with get_async_session() as session:
                for item in pending_list:
                    retry_count = item["retry_count"]
                    last_retry = item["last_retry_at"]
                    
                    # Bounded exponential backoff: 2 ** retry_count seconds
                    delay_sec = 2 ** retry_count
                    if last_retry:
                        elapsed = (now - last_retry).total_seconds()
                        if elapsed < delay_sec:
                            continue  # Wait for backoff window
                            
                    doc_and_meta = await self._fetch_document(session, item["memory_type"], item["record_id"])
                    if not doc_and_meta:
                        # Relational record deleted or missing, fail this metadata entry
                        await self.sqlite_repo.update_metadata_status(item["id"], "failed", False, retry_count, now)
                        continue
                        
                    doc_text, meta = doc_and_meta
                    try:
                        # Generate embedding using active service model
                        embedding = self.embedding_service.get_embeddings(doc_text)
                        
                        # Idempotent save/upsert in ChromaDB
                        self.chroma_repo.save_embedding(
                            memory_id=item["chroma_id"],
                            embedding=embedding,
                            document=doc_text,
                            metadata=meta
                        )
                        
                        # Set metadata active and clear pending flags
                        await self.sqlite_repo.update_metadata_status(item["id"], "active", False, 0, now)
                        logger.info(f"Background Retry: Successfully indexed metadata ID {item['id']} into ChromaDB.")
                    except Exception as ex:
                        # Log failure and increment retry counter
                        next_retry = retry_count + 1
                        status = "pending" if next_retry < settings.MAX_INDEX_RETRIES else "failed"
                        await self.sqlite_repo.update_metadata_status(item["id"], status, True, next_retry, now)
                        logger.error(f"Background Retry Attempt {next_retry} failed for metadata ID {item['id']}: {ex}")
        except Exception as e:
            logger.error(f"Error processing background index retries: {e}", exc_info=True)

    async def _fetch_document(self, session, m_type: str, record_id: int) -> Optional[tuple]:
        """
        Fetches the target database row and reconstructs the document text and metadata mappings.
        """
        if m_type == "fact":
            stmt = select(UserFactModel).where(UserFactModel.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m and not m.is_deleted:
                doc = f"Fact - {m.category}: {m.value}"
                meta = {
                    "memory_type": "fact",
                    "category": m.category,
                    "key": m.key,
                    "value": m.value,
                    "importance": m.importance
                }
                return doc, meta
        elif m_type == "preference":
            stmt = select(PreferenceModel).where(PreferenceModel.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m and not m.is_deleted:
                doc = f"Preference - {m.category}: {m.value}"
                meta = {
                    "memory_type": "preference",
                    "category": m.category,
                    "key": m.key,
                    "value": m.value,
                    "importance": m.importance
                }
                return doc, meta
        elif m_type == "goal":
            stmt = select(GoalModel).where(GoalModel.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m and not m.is_deleted:
                doc = f"Goal - goals: {m.description}"
                meta = {
                    "memory_type": "goal",
                    "category": "goals",
                    "key": m.title,
                    "value": m.description,
                    "importance": m.importance
                }
                return doc, meta
        elif m_type == "note":
            stmt = select(NoteModel).where(NoteModel.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m and not m.is_deleted:
                doc = f"Note - notes: {m.content}"
                meta = {
                    "memory_type": "note",
                    "category": "notes",
                    "key": m.title,
                    "value": m.content,
                    "importance": m.importance
                }
                return doc, meta
        elif m_type == "task":
            stmt = select(TaskModel).where(TaskModel.id == record_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m and not m.is_deleted:
                doc = f"Task - tasks: {m.description}"
                meta = {
                    "memory_type": "task",
                    "category": "tasks",
                    "key": m.title,
                    "value": m.description,
                    "importance": m.importance
                }
                return doc, meta
        return None
