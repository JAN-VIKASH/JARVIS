import logging
from typing import Dict, Any
from app.database.repositories.entity_repository import EntityRepository
from app.database.repositories.relationship_repository import RelationshipRepository

logger = logging.getLogger("jarvis.cognitive.graph")

class GraphStatistics:
    """
    Exposes graph-theory metrics (density, degree, isolated nodes, clusters)
    for telemetry and system diagnostics.
    """
    def __init__(self, entity_repo: EntityRepository, relationship_repo: RelationshipRepository):
        self.entity_repo = entity_repo
        self.relationship_repo = relationship_repo

    async def compute_statistics(self) -> Dict[str, Any]:
        """
        Calculates node counts, edge counts, average degree, density, and connected components.
        """
        entities = await self.entity_repo.list_entities(limit=5000)
        relationships = await self.relationship_repo.find_relationships()
        
        v = len(entities)
        e = len(relationships)
        
        if v == 0:
            return {
                "node_count": 0,
                "relationship_count": 0,
                "average_degree": 0.0,
                "density": 0.0,
                "isolated_nodes_count": 0,
                "connected_components_count": 0
            }

        # Calculate degrees and isolated nodes
        degree_map = {ent["id"]: 0 for ent in entities}
        for r in relationships:
            src = r["source_entity_id"]
            tgt = r["target_entity_id"]
            if src in degree_map:
                degree_map[src] += 1
            if tgt in degree_map:
                degree_map[tgt] += 1
                
        isolated_count = sum(1 for val in degree_map.values() if val == 0)
        avg_degree = sum(degree_map.values()) / v
        
        # Density formula (directed graph): E / (V * (V - 1))
        density = 0.0
        if v > 1:
            density = e / (v * (v - 1))
            
        # Connected components
        components = await self.relationship_repo.get_connected_components()
        
        return {
            "node_count": v,
            "relationship_count": e,
            "average_degree": round(avg_degree, 4),
            "density": round(density, 4),
            "isolated_nodes_count": isolated_count,
            "connected_components_count": len(components)
        }
