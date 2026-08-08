import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from app.database.repositories.entity_repository import EntityRepository
from app.database.repositories.relationship_repository import RelationshipRepository
from app.database.repositories.alias_repository import AliasRepository
from app.database.repositories.user_profile_repository import UserProfileRepository
from app.cognitive.resolution.alias_resolution_engine import AliasResolutionEngine
from app.cognitive.infrastructure.exceptions import GraphException

logger = logging.getLogger("jarvis.cognitive.graph")

class KnowledgeGraphService:
    """
    Coordinates entity inserts, relationship connections, deduplication merges,
    visualizations, statistics, path queries, and transactional updates.
    """
    def __init__(
        self,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository,
        alias_repo: AliasRepository,
        alias_engine: AliasResolutionEngine,
        chroma_repo: Any,  # ChromaMemoryRepository injected via DI
        embedding_service: Any,  # Embedding service injected via DI
        cache_size: int = 128
    ):
        self.entity_repo = entity_repo
        self.relationship_repo = relationship_repo
        self.alias_repo = alias_repo
        self.alias_engine = alias_engine
        self.chroma_repo = chroma_repo
        self.embedding_service = embedding_service
        
        # Cache for neighborhood queries
        self._neighbor_cache = {}
        self._neighbor_cache_keys = []
        self.cache_size = cache_size
        
        self._status = "healthy"
        self._traversals_count = 0
        self._cache_hits = 0

    def get_status(self) -> str:
        return self._status

    def get_telemetry(self) -> Dict[str, Any]:
        hit_ratio = 0.0
        if self._traversals_count > 0:
            hit_ratio = self._cache_hits / self._traversals_count
        return {
            "graph_traversal_count": self._traversals_count,
            "cache_hits": self._cache_hits,
            "cache_hit_ratio": hit_ratio
        }

    def clear_cache(self):
        self._neighbor_cache.clear()
        self._neighbor_cache_keys.clear()
        self.alias_engine.clear_cache()

    def invalidate_cache(self, entity_id: str):
        # Remove cached neighborhood entries for this entity
        if entity_id in self._neighbor_cache:
            self._neighbor_cache_keys.remove(entity_id)
            del self._neighbor_cache[entity_id]

    def _set_neighbor_cache(self, entity_id: str, value: List[Dict[str, Any]]):
        if entity_id in self._neighbor_cache:
            self._neighbor_cache_keys.remove(entity_id)
        elif len(self._neighbor_cache) >= self.cache_size:
            oldest = self._neighbor_cache_keys.pop(0)
            del self._neighbor_cache[oldest]
        self._neighbor_cache[entity_id] = value
        self._neighbor_cache_keys.append(entity_id)

    async def add_entity(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
        confidence: float = 1.0,
        metadata_json: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adds a new entity, resolving aliases, generating semantic embeddings,
        and invalidating affected caches.
        """
        # Resolve alias/canonical name first
        resolved_id = await self.alias_engine.resolve_alias(name, entity_type)
        
        if resolved_id:
            # Entity already exists, increment mentions and return it
            await self.entity_repo.increment_mentions(resolved_id)
            entity = await self.entity_repo.get_entity(resolved_id)
            self.invalidate_cache(resolved_id)
            return entity

        # Create new entity record
        entity = await self.entity_repo.create_entity(
            canonical_name=name,
            entity_type=entity_type,
            description=description,
            confidence=confidence,
            metadata_json=metadata_json
        )
        entity_id = entity["id"]

        # Register default alias
        await self.alias_repo.add_alias(
            entity_id=entity_id,
            alias=name,
            confidence=1.0,
            source="canonical"
        )

        # Generate vector embedding for entity
        doc_text = f"Entity: {name} ({entity_type}) - {description or ''}"
        try:
            embedding = self.embedding_service.get_embeddings(doc_text)
            chroma_id = f"graph_entity_{entity_id}"
            
            # Save embedding in Chroma DB
            self.chroma_repo.save_embedding(
                memory_id=chroma_id,
                embedding=embedding,
                document=doc_text,
                metadata={
                    "type": "graph_entity",
                    "entity_id": entity_id,
                    "canonical_name": name,
                    "entity_type": entity_type
                }
            )
            
            # Update entity model with embedding_id
            await self.entity_repo.update_entity(entity_id, embedding_id=chroma_id)
            entity["embedding_id"] = chroma_id
        except Exception as e:
            logger.error(f"Failed to generate embedding for entity {name}: {e}")

        # Invalidate resolved cache
        self.alias_engine.invalidate_key(name)
        return entity

    async def add_relationship(
        self,
        source_name: str,
        source_type: str,
        target_name: str,
        target_type: str,
        relation_type: str,
        confidence: float = 1.0,
        weight: float = 1.0,
        bidirectional: bool = False,
        evidence_memory_id: Optional[str] = None,
        source_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates or updates a connecting relationship between two entities.
        """
        # Ensure both entities exist or create them
        source_ent = await self.add_entity(source_name, source_type)
        target_ent = await self.add_entity(target_name, target_type)
        
        source_id = source_ent["id"]
        target_id = target_ent["id"]
        
        # Check if relation already exists
        rel = await self.relationship_repo.relationship_exists(source_id, target_id, relation_type)
        if rel:
            # Update weight and confidence
            updated_rel = await self.relationship_repo.update_relationship(
                relationship_id=rel["id"],
                confidence=max(rel["confidence"], confidence),
                weight=max(rel["weight"], weight),
                evidence_memory_id=evidence_memory_id
            )
            self.invalidate_cache(source_id)
            self.invalidate_cache(target_id)
            return updated_rel

        # Create new relationship
        new_rel = await self.relationship_repo.create_relationship(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=relation_type,
            confidence=confidence,
            weight=weight,
            bidirectional=bidirectional,
            evidence_memory_id=evidence_memory_id,
            source_session_id=source_session_id
        )
        
        self.invalidate_cache(source_id)
        self.invalidate_cache(target_id)
        return new_rel

    async def delete_entity_safely(self, entity_id: str) -> bool:
        """
        Deletes an entity along with associated aliases and relationships to prevent orphaned nodes.
        Updates ChromaDB indices and flushes cached maps.
        """
        # Delete aliases
        aliases = await self.alias_repo.list_aliases(entity_id)
        for al in aliases:
            await self.alias_repo.remove_alias(al["id"])
            self.alias_engine.invalidate_key(al["alias"])

        # Delete relationships pointing to/from this entity
        rels = await self.relationship_repo.find_relationships(source_id=entity_id)
        for r in rels:
            await self.relationship_repo.delete_relationship(r["id"])
            self.invalidate_cache(r["target_entity_id"])
            
        rels_in = await self.relationship_repo.find_relationships(target_id=entity_id)
        for r in rels_in:
            await self.relationship_repo.delete_relationship(r["id"])
            self.invalidate_cache(r["source_entity_id"])

        # Invalidate current cache
        self.invalidate_cache(entity_id)

        # Delete vector embeddings from ChromaDB
        try:
            self.chroma_repo.collection.delete(ids=[f"graph_entity_{entity_id}"])
        except Exception as e:
            logger.warning(f"ChromaDB delete failed for graph_entity_{entity_id}: {e}")

        # Delete entity record from SQL database
        return await self.entity_repo.delete_entity(entity_id)

    async def query(self, entity: str, relation: Optional[str] = None, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Implements a unified Graph Query Language interface lookup for entity relationships.
        Supports multi-hop expansion with cycle safety checks.
        """
        self._traversals_count += 1
        resolved_id = await self.alias_engine.resolve_alias(entity)
        if not resolved_id:
            return []

        visited = set()
        results = []
        await self._recursive_query(resolved_id, relation, depth, visited, results)
        return results

    async def _recursive_query(
        self,
        entity_id: str,
        relation_filter: Optional[str],
        depth: int,
        visited: Set[str],
        results: List[Dict[str, Any]]
    ):
        if depth <= 0 or entity_id in visited:
            return
            
        visited.add(entity_id)
        
        # Check cache for neighbors
        if entity_id in self._neighbor_cache:
            self._cache_hits += 1
            neighbors = self._neighbor_cache[entity_id]
        else:
            neighbors = await self.relationship_repo.find_neighbors(entity_id)
            self._set_neighbor_cache(entity_id, neighbors)

        for n in neighbors:
            # Apply relation type filter if provided
            if relation_filter and n["relation_type"] != relation_filter.strip().upper():
                continue
                
            n_entity = await self.entity_repo.get_entity(n["entity_id"])
            if n_entity:
                results.append({
                    "relationship_id": n["relationship_id"],
                    "relation_type": n["relation_type"],
                    "direction": n["direction"],
                    "entity": n_entity
                })
                
                # Expand search recursively
                await self._recursive_query(n["entity_id"], relation_filter, depth - 1, visited, results)

    async def expand_context(self, entities_list: List[str], max_depth: int = 2) -> List[str]:
        """
        Expands the graph neighborhood of given seed entities and returns textual facts.
        Uses semantic neighbor ranking to keep facts high quality.
        """
        facts = []
        visited = set()
        
        for name in entities_list:
            resolved_id = await self.alias_engine.resolve_alias(name)
            if not resolved_id:
                continue
                
            # Perform query at depth
            neighbors = await self.query(entity=name, depth=max_depth)
            
            # Rank neighboring nodes (combining relation weight & extraction confidence)
            neighbors.sort(key=lambda x: (x["entity"]["confidence"] * 0.4 + x["relation_type"] != "RELATED_TO"), reverse=True)
            
            for item in neighbors:
                ent = item["entity"]
                ent_name = ent["canonical_name"]
                rel_type = item["relation_type"]
                direction = item["direction"]
                
                fact_key = (resolved_id, ent["id"], rel_type)
                if fact_key not in visited:
                    visited.add(fact_key)
                    if direction == "out":
                        facts.append(f"{name} {rel_type} {ent_name} ({ent['description'] or ''})")
                    else:
                        facts.append(f"{ent_name} {rel_type} {name} ({ent['description'] or ''})")
                        
        return facts[:15]  # cap to top 15 highest-ranked facts
