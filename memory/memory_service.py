"""
MemoryService coordinator class for SQLite and ChromaDB memory orchestration.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from memory.sqlite_repository import SQLiteMemoryRepository
from memory.chroma_repository import ChromaMemoryRepository
from memory.filter import MemoryFilter
from memory.embedding import EmbeddingService
from memory.scorer import ImportanceScorer
from memory.extractor import MemoryExtractor
from memory.search import MemorySearchService
from memory.conflict_resolver import MemoryConflictResolver
from memory.decay_service import MemoryDecayService

logger = logging.getLogger("jarvis.memory")

class MemoryService:
    """
    Main coordinator service managing conversation logging, fact extraction, 
    embeddings, semantic indexing, and context compilation.
    """
    def __init__(
        self,
        sqlite_repo: SQLiteMemoryRepository,
        chroma_repo: ChromaMemoryRepository,
        memory_filter: MemoryFilter,
        embedding_service: EmbeddingService,
        scorer: ImportanceScorer,
        extractor: MemoryExtractor,
        search_service: MemorySearchService,
        conflict_resolver: MemoryConflictResolver,
        decay_service: MemoryDecayService,
        event_repository: Optional[Any] = None,
        event_extractor: Optional[Any] = None,
        
        # Phase 5.2 graph injects
        graph_extractor: Optional[Any] = None,
        graph_service: Optional[Any] = None,
        user_profile_engine: Optional[Any] = None,
        pronoun_resolver: Optional[Any] = None,
        background_job_manager: Optional[Any] = None
    ):
        self.sqlite_repo = sqlite_repo
        self.chroma_repo = chroma_repo
        self.memory_filter = memory_filter
        self.embedding_service = embedding_service
        self.scorer = scorer
        self.extractor = extractor
        self.search_service = search_service
        self.conflict_resolver = conflict_resolver
        self.decay_service = decay_service
        
        # Phase 5.1 Temporal Reasoning dependencies
        if event_repository:
            self.event_repository = event_repository
        else:
            from app.database.repositories.event_repository import EventRepository
            self.event_repository = EventRepository()
            
        if event_extractor:
            self.event_extractor = event_extractor
        else:
            try:
                from app.services.factory import ServiceFactory
                from app.services.cognitive.event_extractor import EventExtractor
                llm = ServiceFactory.get_llm()
                self.event_extractor = EventExtractor(llm)
            except Exception as e:
                logger.warning(f"Could not load LLM event extractor for MemoryService (events will be disabled): {e}")
                self.event_extractor = None

        # Phase 5.1.1 Event lifecycle additions
        try:
            from app.services.factory import ServiceFactory
            from app.services.cognitive.event_update_detector import EventUpdateDetector
            from app.services.cognitive.duplicate_event_resolver import DuplicateEventResolver
            llm = ServiceFactory.get_llm()
            self.event_update_detector = EventUpdateDetector(llm, self.event_repository)
            self.duplicate_resolver = DuplicateEventResolver(self.event_repository)
        except Exception as e:
            logger.warning(f"Could not load Advanced Event lifecycle components for MemoryService: {e}")
            self.event_update_detector = None
            self.duplicate_resolver = None

        # Phase 5.2 Knowledge Graph & User Profile assignments
        self.graph_extractor = graph_extractor
        self.graph_service = graph_service
        self.user_profile_engine = user_profile_engine
        self.pronoun_resolver = pronoun_resolver
        self.background_job_manager = background_job_manager
        from memory.memory_factory import MemoryFactory
        self.entity_repo = MemoryFactory.get_entity_repo()

        if not self.background_job_manager:
            try:
                from app.cognitive.infrastructure.background_job_manager import BackgroundJobManager
                self.background_job_manager = BackgroundJobManager()
                self.background_job_manager.start()
            except Exception as e:
                logger.warning(f"Could not load BackgroundJobManager in MemoryService: {e}")

    def start(self) -> None:
        """
        Starts any background loops or daemons. Safe to be called after event loop is running.
        """
        self.decay_service.start(interval_seconds=60)

    async def shutdown(self) -> None:
        """
        Gracefully terminates background processes and tasks to avoid orphaned writes.
        """
        await self.decay_service.stop()

    async def save_exchange(self, session_id: str, user_msg: str, assistant_response: str) -> None:
        """
        Triggers conversation exchange saving asynchronously in a background task.
        """
        if not self.memory_filter.should_persist(user_msg):
            return
            
        # Spawn safe non-blocking background task
        asyncio.create_task(self._async_save_exchange(session_id, user_msg, assistant_response))

    async def _async_save_exchange(self, session_id: str, user_msg: str, assistant_response: str) -> None:
        """
        Saves conversations relatiionally first, then indexes vector embeddings in ChromaDB.
        """
        try:
            # 1. Relational SQLite write completes first
            user_conv = await self.sqlite_repo.save_conversation(session_id, "user", user_msg)
            await self.sqlite_repo.save_conversation(session_id, "assistant", assistant_response)
            
            # 2. Reconstruct document for ChromaDB
            combined_text = f"User: {user_msg}\nAssistant: {assistant_response}"
            chroma_id = f"conv_{user_conv['id']}"
            
            # Create indexing metadata flagged as pending_index = True
            model_name = self.embedding_service.model_name
            meta_record = await self.sqlite_repo.save_metadata(
                memory_type="conversation",
                record_id=user_conv["id"],
                chroma_id=chroma_id,
                importance=30,
                embedding_model=model_name,
                pending_index=True
            )
            
            # 3. Compute embeddings and index vector (runs second)
            try:
                embedding = self.embedding_service.get_embeddings(combined_text)
                self.chroma_repo.save_embedding(
                    memory_id=chroma_id,
                    embedding=embedding,
                    document=combined_text,
                    metadata={
                        "memory_type": "conversation",
                        "session_id": session_id,
                        "importance": 30
                    }
                )
                # Successful index: clear pending index flags
                await self.sqlite_repo.update_metadata_status(
                    meta_record["id"],
                    status="active",
                    pending_index=False,
                    retry_count=0,
                    last_retry_at=datetime.utcnow()
                )
            except Exception as index_err:
                logger.error(f"ChromaDB indexing failed for conversation {user_conv['id']}. Marked as pending: {index_err}")
        except Exception as e:
            logger.error(f"Error in background task _async_save_exchange: {e}", exc_info=True)

    async def extract_and_save_memories(self, text: str, session_id: str = "default") -> None:
        """
        Triggers structured memory and event extraction asynchronously in background tasks.
        """
        # 1. Extract and save timeline events
        if self.event_extractor:
            asyncio.create_task(self.extract_and_save_events(session_id, text))

        # 2. Extract facts/preferences
        if self.memory_filter.should_persist(text):
            # Spawn safe non-blocking background task
            asyncio.create_task(self._async_extract_and_save(text, session_id))
            
        # Phase 5.2: Knowledge Graph & User Profile Extraction
        if self.background_job_manager:
            self.background_job_manager.enqueue_job(self._process_graph_and_profile_background, text, session_id)
        else:
            asyncio.create_task(self._process_graph_and_profile_background(text, session_id))

    async def extract_and_save_events(self, session_id: str, text: str) -> None:
        """
        Runs event extraction, lifecycle update detection, duplicate resolution,
        and triggers semantic ChromaDB indexing asynchronously in a background pipeline.
        """
        try:
            # 1. Extractor LLM call
            ref_time = datetime.utcnow()
            events = await self.event_extractor.extract_events(text, ref_time)
            if not events:
                return

            # 2. Update detector LLM call
            op_info = {"operation": "CREATE", "matched_event_id": None, "confidence": 1.0}
            if self.event_update_detector:
                op_info = await self.event_update_detector.detect(session_id, text)

            operation = op_info["operation"]
            matched_id = op_info["matched_event_id"]
            
            for event in events:
                saved_event = None
                
                # Check status modifications
                if operation == "CANCEL" and matched_id:
                    saved_event = await self.event_repository.update_event_status(matched_id, "cancelled")
                elif operation == "COMPLETE" and matched_id:
                    saved_event = await self.event_repository.update_event_status(matched_id, "completed")
                elif operation in ("UPDATE", "POSTPONE") and matched_id:
                    saved_event = await self.event_repository.update_event(
                        event_id=matched_id,
                        title=event["title"],
                        description=event.get("description"),
                        event_type=event.get("event_type"),
                        start_time=event["start_time"],
                        end_time=event.get("end_time"),
                        is_all_day=event.get("is_all_day", False),
                        status="planned" if operation == "UPDATE" else "postponed",
                        importance=event.get("importance", "medium"),
                        confidence=event.get("confidence", 0.8),
                        raw_text=text
                    )
                else:
                    # operation == "CREATE" or matched_id is None
                    # Run Duplicate Resolver
                    duplicate = None
                    if self.duplicate_resolver:
                        duplicate = await self.duplicate_resolver.resolve_duplicate(
                            session_id=session_id,
                            title=event["title"],
                            start_time=event["start_time"],
                            event_type=event.get("event_type")
                        )
                        
                    if duplicate:
                        saved_event = await self.event_repository.update_event(
                            event_id=duplicate["id"],
                            title=event["title"],
                            description=event.get("description") or duplicate.get("description"),
                            event_type=event.get("event_type") or duplicate.get("event_type"),
                            start_time=event["start_time"],
                            end_time=event.get("end_time") or duplicate.get("end_time"),
                            is_all_day=event.get("is_all_day", False),
                            status=duplicate["status"],
                            importance=event.get("importance", "medium"),
                            confidence=event.get("confidence", 0.8),
                            raw_text=text
                        )
                    else:
                        saved_event = await self.event_repository.save_event(
                            session_id=session_id,
                            title=event["title"],
                            description=event.get("description"),
                            event_type=event.get("event_type"),
                            start_time=event["start_time"],
                            end_time=event.get("end_time"),
                            is_all_day=event.get("is_all_day", False),
                            raw_text=text,
                            status="planned",
                            importance=event.get("importance", "medium"),
                            confidence=event.get("confidence", 0.8)
                        )
                
                # 3. Generate embedding and store in ChromaDB
                if saved_event:
                    logger.info(
                        f"Event processed ({operation}): '{saved_event['title']}' "
                        f"for session: '{session_id}' (version: {saved_event['version']})"
                    )
                    
                    try:
                        doc_text = (
                            f"Event: {saved_event['title']} ({saved_event['event_type']}) "
                            f"status {saved_event['status']} importance {saved_event['importance']} "
                            f"starting at {saved_event['start_time'].isoformat()}."
                        )
                        embedding = self.embedding_service.get_embeddings(doc_text)
                        chroma_id = f"event_{saved_event['id']}"
                        
                        self.chroma_repo.save_embedding(
                            memory_id=chroma_id,
                            embedding=embedding,
                            document=doc_text,
                            metadata={
                                "type": "event",
                                "session_id": session_id,
                                "title": saved_event["title"],
                                "event_id": saved_event["id"]
                            }
                        )
                        
                        await self.event_repository.update_embedding_id(saved_event["id"], chroma_id)
                    except Exception as embed_err:
                        logger.error(f"Failed to generate event embedding/index: {embed_err}")
                        
        except Exception as e:
            logger.error(f"Failed in advanced event pipeline: {e}", exc_info=True)

    async def _async_extract_and_save(self, text: str, session_id: str = "default") -> None:
        """
        Runs hybrid extractors and resolves conflicts, deactivating duplicates and saving.
        """
        try:
            # Stage 1 Regex + Stage 2 LLM extraction (Hybrid Extraction)
            extracted = await self.extractor.extract(text)
            if not extracted:
                return
                
            score = self.scorer.score(text)
            
            for item in extracted:
                m_type = item["type"]
                category = item["category"]
                key = item["key"]
                value = item["value"]
                confidence = item.get("confidence", 1.0)
                
                # 1. SQL write resolves conflicts (optimistic locking, versioning, list splits)
                record = await self.conflict_resolver.resolve_and_save(
                    m_type=m_type,
                    category=category,
                    key=key,
                    value=value,
                    confidence=confidence,
                    score=score,
                    session_id=session_id
                )
                record_id = record.get("id")
                if not record_id:
                    continue
                    
                # 2. ChromaDB indexing (runs second)
                doc_text = f"{m_type.capitalize()} - {category}: {value}"
                chroma_id = f"{m_type}_{record_id}_{key}"
                
                # Create indexing metadata flagged as pending_index = True
                model_name = self.embedding_service.model_name
                meta_record = await self.sqlite_repo.save_metadata(
                    memory_type=m_type,
                    record_id=record_id,
                    chroma_id=chroma_id,
                    importance=score,
                    embedding_model=model_name,
                    pending_index=True
                )
                
                try:
                    embedding = self.embedding_service.get_embeddings(doc_text)
                    self.chroma_repo.save_embedding(
                        memory_id=chroma_id,
                        embedding=embedding,
                        document=doc_text,
                        metadata={
                            "memory_type": m_type,
                            "category": category,
                            "key": key,
                            "value": value,
                            "importance": score
                        }
                    )
                    # Successful index: clear pending index flags
                    await self.sqlite_repo.update_metadata_status(
                        meta_record["id"],
                        status="active",
                        pending_index=False,
                        retry_count=0,
                        last_retry_at=datetime.utcnow()
                    )
                except Exception as index_err:
                    logger.error(f"ChromaDB indexing failed for memory {chroma_id}. Marked as pending: {index_err}")
        except Exception as e:
            logger.error(f"Error in background task _async_extract_and_save: {e}", exc_info=True)

    async def retrieve_context(self, query: str, session_id: Optional[str] = None) -> str:
        """
        Retrieves context string compiling matching similar semantic memories.
        """
        try:
            results = await self.search_service.search_similar_memories(query)
            if not results:
                return ""
                
            context_lines = []
            for res in results:
                m_type = res["memory_type"]
                doc = res["document"]
                
                # Retrieve matching context without leaking scores or metadata headers
                if m_type == "conversation":
                    context_lines.append(f"[Past Conversation]:\n{doc}")
                else:
                    context_lines.append(f"[Memory (category: {res['category']})]: {res['value']}")
                    
            if results:
                asyncio.create_task(self.track_access_and_learn(query, results))
            return "\n".join(context_lines)
        except Exception as e:
            logger.error(f"Failure Isolation: Context retrieval error ignored: {e}", exc_info=True)
            return ""

    async def retrieve_long_term_context(self, query: str) -> str:
        """
        Layer 3 context compiler. Formats SQLite facts, preferences, goals, notes, and tasks.
        """
        try:
            results = await self.search_service.search_relational_memories(query)
            if not results:
                return ""
            lines = []
            for res in results:
                m_type = res["memory_type"]
                if m_type in ("fact", "preference"):
                    lines.append(f"[Long-Term Memory ({m_type}: {res.get('category')})]: {res.get('key')} = {res.get('value')}")
                elif m_type in ("goal", "task"):
                    lines.append(f"[Long-Term Memory ({m_type})]: {res.get('title')} - {res.get('description')} (status: {res.get('status')})")
                elif m_type == "note":
                    lines.append(f"[Long-Term Memory (note)]: {res.get('title')} - {res.get('content')}")
            if results:
                asyncio.create_task(self.track_access_and_learn(query, results))
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error compiling Layer 3 long-term context: {e}", exc_info=True)
            return ""

    async def retrieve_semantic_context(self, query: str) -> str:
        """
        Layer 4 context compiler. Formats ChromaDB past conversations semantic matches.
        """
        try:
            results = await self.search_service.search_semantic_memories(query)
            if not results:
                return ""
            lines = []
            for res in results:
                lines.append(f"[Past Conversation]:\n{res['document']}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error compiling Layer 4 semantic context: {e}", exc_info=True)
            return ""

    async def _process_graph_and_profile_background(self, text: str, session_id: str) -> None:
        """
        Processes knowledge graph extractions and user profile updates.
        """
        try:
            from app.config.settings import settings
            
            resolved_text = text
            # 1. Pronoun Resolution
            if settings.ENABLE_ALIAS_RESOLUTION and self.pronoun_resolver:
                try:
                    recent_convs = await self.sqlite_repo.get_recent_conversations(session_id, limit=5)
                    recent_msg_list = [{"role": c["role"], "content": c["content"]} for c in recent_convs]
                    referent = await self.pronoun_resolver.resolve_referent(text, recent_msg_list)
                    if referent:
                        resolved_text += f"\n(Context Note: Referring to {referent['canonical_name']} ({referent['entity_type']}))"
                except Exception as ex_pronoun:
                    logger.warning(f"Pronoun resolution check failed: {ex_pronoun}")

            # 2. Entity & Relationship Extraction
            if settings.ENABLE_GRAPH and self.graph_extractor and self.graph_service:
                try:
                    extracted = await self.graph_extractor.extract_graph(resolved_text)
                    # Create entities
                    for ent in extracted.get("entities", []):
                        await self.graph_service.add_entity(
                            name=ent["name"],
                            entity_type=ent["type"],
                            description=ent.get("description"),
                            confidence=ent.get("confidence", 1.0)
                        )
                    # Create relationships
                    for rel in extracted.get("relationships", []):
                        await self.graph_service.add_relationship(
                            source_name=rel["source"],
                            source_type="generic",
                            target_name=rel["target"],
                            target_type="generic",
                            relation_type=rel["type"],
                            confidence=rel.get("confidence", 1.0),
                            weight=rel.get("weight", 1.0),
                            source_session_id=session_id
                        )
                except Exception as ex_graph:
                    logger.error(f"Asynchronous graph extraction failed: {ex_graph}", exc_info=True)

            # 3. User Profile Evolution
            if settings.ENABLE_USER_PROFILE and self.user_profile_engine:
                try:
                    await self.user_profile_engine.extract_and_update_profile(resolved_text, session_id)
                except Exception as ex_profile:
                    logger.error(f"Asynchronous user profile update failed: {ex_profile}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error in background graph/profile task: {e}", exc_info=True)

    async def track_access_and_learn(self, query: str, retrieved_records: List[Dict[str, Any]]) -> None:
        """
        Calculates and applies adaptive importance updates to database records.
        """
        if not retrieved_records:
            return
            
        try:
            # 1. Update access statistics (pure access tracking)
            type_id_pairs = []
            for rec in retrieved_records:
                m_type = rec.get("memory_type")
                record_id = rec.get("record_id") or rec.get("id")
                if m_type and record_id:
                    type_id_pairs.append((m_type, record_id))
            
            if type_id_pairs:
                await self.sqlite_repo.record_accesses(type_id_pairs)

            # 2. Run Adaptive Importance score calculations
            from memory.memory_factory import MemoryFactory
            adaptive_learner = MemoryFactory.get_adaptive_learner()
            
            for rec in retrieved_records:
                m_type = rec.get("memory_type")
                record_id = rec.get("record_id") or rec.get("id")
                similarity = rec.get("similarity", 0.7) # fallback default relevance
                
                if m_type and record_id and m_type in ("fact", "preference", "note", "goal", "task"):
                    db_record = await self.sqlite_repo.get_record_by_id_and_type(m_type, record_id)
                    if db_record:
                        current_importance = db_record.get("importance", 50)
                        access_count = db_record.get("access_count", 0)
                        
                        new_importance = adaptive_learner.compute_adaptive_score(
                            current_importance=current_importance,
                            access_count=access_count,
                            relevance_score=similarity,
                            user_query=query
                        )
                        
                        if new_importance != current_importance:
                            await self.sqlite_repo.update_importance(m_type, record_id, new_importance)
        except Exception as e:
            logger.error(f"Failed in track_access_and_learn task: {e}", exc_info=True)

    async def set_active_status(self, m_type: str, record_id: int, is_active: bool) -> bool:
        """
        Toggles the active status of a memory record.
        """
        return await self.sqlite_repo.set_memory_active_status(m_type, record_id, is_active)

    async def archive_memory(self, m_type: str, record_id: int, is_archived: bool = True) -> bool:
        """
        Toggles the archived status of a memory record.
        """
        return await self.sqlite_repo.set_memory_archived_status(m_type, record_id, is_archived)

    async def delete_memory_permanently(self, m_type: str, record_id: int) -> bool:
        """
        Permanently deletes a memory record by removing it from the database.
        """
        # Also clean up from vector search if possible
        if self.chroma_repo:
            chroma_id = f"{m_type}_{record_id}"
            try:
                self.chroma_repo.delete_embedding(chroma_id)
            except Exception as e:
                logger.warning(f"Failed to delete ChromaDB index {chroma_id} during permanent delete: {e}")
        return await self.sqlite_repo.delete_memory_permanently(m_type, record_id)

