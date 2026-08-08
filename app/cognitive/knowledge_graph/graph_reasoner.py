import logging
from typing import List, Dict, Any, Optional
from app.cognitive.knowledge_graph.knowledge_graph_service import KnowledgeGraphService
from app.database.repositories.entity_repository import EntityRepository
from app.database.repositories.relationship_repository import RelationshipRepository

logger = logging.getLogger("jarvis.cognitive.graph")

class GraphReasoner:
    """
    Solves semantic multi-hop reasoning queries across relationship paths in the Knowledge Graph.
    """
    def __init__(
        self,
        graph_service: KnowledgeGraphService,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository
    ):
        self.graph_service = graph_service
        self.entity_repo = entity_repo
        self.relationship_repo = relationship_repo

    async def reason_relation_chain(
        self,
        start_entity_name: str,
        relation_chain: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Traverses a chain of relations (e.g., ["WORKS_ON", "USES"]) starting from an entity.
        Returns a list of target entities discovered at the end of the multi-hop chain.
        """
        # Resolve starting entity
        resolved_id = await self.graph_service.alias_engine.resolve_alias(start_entity_name)
        if not resolved_id:
            return []
            
        current_node_ids = {resolved_id}
        
        for rel_type in relation_chain:
            next_node_ids = set()
            rel_upper = rel_type.strip().upper()
            
            for node_id in current_node_ids:
                # Find relationships where node_id is the source
                rels = await self.relationship_repo.find_relationships(source_id=node_id, rel_type=rel_upper)
                for r in rels:
                    next_node_ids.add(r["target_entity_id"])
                    
                # If bidirectional relation is possible, check target connections too
                rels_rev = await self.relationship_repo.find_relationships(target_id=node_id, rel_type=rel_upper)
                for r in rels_rev:
                    if r["bidirectional"]:
                        next_node_ids.add(r["source_entity_id"])
                        
            current_node_ids = next_node_ids
            if not current_node_ids:
                break
                
        # Resolve node IDs to full entity records
        result_entities = []
        for entity_id in current_node_ids:
            ent = await self.entity_repo.get_entity(entity_id)
            if ent:
                result_entities.append(ent)
                
        return result_entities
