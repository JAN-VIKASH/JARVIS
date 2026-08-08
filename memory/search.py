"""
Search service to query and compile context memories.
"""
import math
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config.settings import settings
from memory.chroma_repository import ChromaMemoryRepository
from memory.sqlite_repository import SQLiteMemoryRepository
from memory.embedding import EmbeddingService

logger = logging.getLogger("jarvis.memory")

class MemorySearchService:
    """
    Coordinates semantic vector searches against ChromaDB, matches relational records,
    calculates weighted scores, and deduplicates matching results.
    """
    def __init__(
        self,
        chroma_repo: ChromaMemoryRepository,
        sqlite_repo: SQLiteMemoryRepository,
        embedding_service: EmbeddingService
    ):
        self.chroma_repo = chroma_repo
        self.sqlite_repo = sqlite_repo
        self.embedding_service = embedding_service

    async def search_similar_memories(
        self,
        query: str,
        limit: int = None,
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Queries ChromaDB, loads SQL metadata, computes weighted ranking, and filters results.
        """
        if not query:
            return []
            
        limit = limit or settings.MEMORY_TOP_K
        threshold = threshold or settings.SIMILARITY_THRESHOLD
        
        # 1. Compute query embeddings
        try:
            query_emb = self.embedding_service.get_embeddings(query)
            if not query_emb:
                return []
        except Exception as e:
            logger.error(f"Failed to generate search embeddings: {e}")
            return []

        # 2. Search ChromaDB for vector candidates
        try:
            raw_results = self.chroma_repo.search_similar(query_emb, limit=limit * 4)
        except Exception as e:
            logger.error(f"Failed to search ChromaDB: {e}")
            return []
            
        query_lower = query.lower()
        include_inactive = any(w in query_lower for w in ["history", "previous", "previously", "version", "before", "earlier", "formerly", "past"])
        include_archived = any(w in query_lower for w in ["archive", "archived", "past", "historical"])

        # 3. Match SQL records and compute weighted scores
        scored_results = []
        for res in raw_results:
            distance = res.get("distance", 1.0)
            similarity = 1.0 / (1.0 + distance)
            
            if similarity < threshold:
                continue
                
            # Parse record ID and type from Chroma ID
            chroma_id = res["id"]
            parts = chroma_id.split("_")
            if not parts:
                continue
                
            m_type_raw = parts[0]
            m_type = "conversation" if m_type_raw == "conv" else m_type_raw
            
            try:
                record_id = int(parts[1])
            except (IndexError, ValueError):
                continue
                
            # Fetch relational details
            record = await self.sqlite_repo.get_record_by_id_and_type(m_type, record_id)
            if not record or record.get("is_deleted"):
                continue
                
            # Version filter
            if not include_inactive and not record.get("is_active", True):
                continue
                
            # Archive filter
            if not include_archived and record.get("is_archived", False):
                continue

            # Compute weighted ranking components
            importance = float(record.get("importance", 50)) / 100.0
            confidence = float(record.get("confidence", 1.0))
            
            # Recency calculation
            updated_at = record.get("updated_at") or datetime.utcnow()
            days_since_updated = max(0, (datetime.utcnow() - updated_at).days)
            recency_score = math.exp(-0.05 * days_since_updated)
            
            # Frequency score
            access_count = float(record.get("access_count", 0))
            frequency_score = access_count / (access_count + 2.0)
            
            # Combine weights
            score = (
                settings.RANKING_WEIGHT_SIMILARITY * similarity +
                settings.RANKING_WEIGHT_IMPORTANCE * importance +
                settings.RANKING_WEIGHT_CONFIDENCE * confidence +
                settings.RANKING_WEIGHT_RECENCY * recency_score +
                settings.RANKING_WEIGHT_FREQUENCY * frequency_score
            )
            
            scored_results.append({
                "chroma_id": chroma_id,
                "record_id": record_id,
                "memory_type": m_type,
                "category": record.get("category", ""),
                "key": record.get("key", ""),
                "value": record.get("value", ""),
                "document": res["document"],
                "similarity": similarity,
                "final_score": score,
                "is_archived": record.get("is_archived", False),
                "is_active": record.get("is_active", True),
                "version": record.get("version", 1)
            })

        # 4. Deduplicate matches: keep the highest final_score representation for duplicate entity keys
        seen_keys = set()
        deduplicated = []
        
        # Sort candidates prioritizing active first, then newest version, then highest score
        scored_results.sort(key=lambda x: (x["is_active"], x["version"], x["final_score"]), reverse=True)
        
        for item in scored_results:
            if item["memory_type"] in ("fact", "preference"):
                dup_key = f"{item['memory_type']}:{item['category']}:{item['key']}"
                if include_inactive:
                    dup_key = f"{dup_key}:{item.get('version', 1)}"
                if dup_key in seen_keys:
                    continue
                seen_keys.add(dup_key)
            else:
                doc_key = item["document"].strip().lower()
                if doc_key in seen_keys:
                    continue
                seen_keys.add(doc_key)
                
            deduplicated.append(item)
            
        # Select the top limit items
        final_selections = deduplicated[:limit]
        
        # 5. Non-blocking retrieval metadata updates (access logs, unarchiving)
        for item in final_selections:
            # Table mapping helper
            t_mapping = {
                "fact": "user_facts",
                "preference": "preferences",
                "goal": "goals",
                "task": "tasks",
                "note": "notes",
                "conversation": "conversations"
            }
            table_name = t_mapping.get(item["memory_type"])
            if table_name:
                try:
                    await self.sqlite_repo.update_access_metrics(table_name, item["record_id"])
                    # Reversible archiving update: update memory state in item dictionary
                    if item["is_archived"]:
                        item["is_archived"] = False
                except Exception as ex:
                    logger.warning(f"Failed updating access logs during search: {ex}")
                    
        return final_selections

    async def search_relational_memories(self, query: str, limit: int = 5, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Layer 3: Long-Term Memory. Search SQLite directly for facts, preferences, goals, tasks, notes using keyword matches.
        """
        import re
        clean_query = re.sub(r'[^\w\s]', '', query)
        stop_words = {
            "what", "was", "who", "where", "when", "why", "how", "did", "does", "do",
            "the", "and", "but", "for", "with", "this", "that", "these", "those",
            "you", "your", "my", "mine", "his", "her", "they", "them", "their", "are", "is", "were", "been", "have", "has", "had"
        }
        keywords = [
            w.strip() for w in clean_query.split()
            if len(w.strip()) > 2 and w.strip().lower() not in stop_words
        ]
        if not keywords:
            keywords = [query]
            
        query_lower = query.lower()
        include_inactive = any(w in query_lower for w in ["history", "previous", "previously", "version", "before", "earlier", "formerly", "past"])
        include_archived = any(w in query_lower for w in ["archive", "archived", "past", "historical"])

        all_results = []
        for kw in keywords[:3]:
            facts = await self.sqlite_repo.search_facts(kw, limit=limit, include_inactive=include_inactive, include_archived=include_archived)
            prefs = await self.sqlite_repo.search_preferences(kw, limit=limit, include_inactive=include_inactive, include_archived=include_archived)
            goals = await self.sqlite_repo.search_goals(kw, limit=limit)
            tasks = await self.sqlite_repo.search_tasks(session_id, kw, limit=limit)
            notes = await self.sqlite_repo.search_notes(kw, limit=limit)
            
            for item in facts:
                item["memory_type"] = "fact"
                all_results.append(item)
            for item in prefs:
                item["memory_type"] = "preference"
                all_results.append(item)
            for item in goals:
                item["memory_type"] = "goal"
                all_results.append(item)
            for item in tasks:
                item["memory_type"] = "task"
                all_results.append(item)
            for item in notes:
                item["memory_type"] = "note"
                all_results.append(item)
                
        # Prioritize active records and higher versions during relational deduplication
        all_results.sort(key=lambda x: (x.get("is_active", True), x.get("version", 1)), reverse=True)
        
        seen = set()
        deduped = []
        for item in all_results:
            key_name = item.get("key", item.get("title", ""))
            ukey = (item["memory_type"], item.get("category", ""), key_name)
            if include_inactive:
                ukey = (item["memory_type"], item.get("category", ""), key_name, item.get("version", 1))
            if ukey not in seen:
                seen.add(ukey)
                deduped.append(item)
                
        return deduped[:limit]

    async def search_semantic_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Layer 4: Semantic Memory. Queries ChromaDB for past conversation dialogue segments using semantic vector search.
        """
        query_emb = self.embedding_service.get_embeddings(query)
        if not query_emb:
            return []
            
        try:
            raw = self.chroma_repo.search_similar(query_emb, limit=limit * 3)
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
            
        results = []
        for res in raw:
            meta = res.get("metadata", {})
            m_type = meta.get("memory_type")
            if m_type == "conversation":
                distance = res.get("distance", 1.0)
                sim = 1.0 / (1.0 + distance)
                if sim >= settings.SIMILARITY_THRESHOLD:
                    results.append({
                        "document": res["document"],
                        "similarity": sim
                    })
                    
        seen = set()
        deduped = []
        for item in results:
            doc_clean = item["document"].strip().lower()
            if doc_clean not in seen:
                seen.add(doc_clean)
                deduped.append(item)
                
        return deduped[:limit]
