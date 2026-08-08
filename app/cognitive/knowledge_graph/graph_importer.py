import json
import logging
from typing import Dict, Any
from app.cognitive.knowledge_graph.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger("jarvis.cognitive.graph")

class GraphImporter:
    """
    Parses and restores a knowledge graph backup from a unified JSON schema.
    """
    def __init__(self, graph_service: KnowledgeGraphService):
        self.graph_service = graph_service

    async def import_from_json(self, json_data: str) -> Dict[str, int]:
        """
        Parses JSON graph state and upserts nodes and edges.
        Returns counts of imported entities and relationships.
        """
        try:
            parsed = json.loads(json_data)
        except Exception as e:
            logger.error(f"Failed to parse JSON for graph import: {e}")
            raise ValueError(f"Invalid JSON string: {e}")
            
        nodes = parsed.get("nodes", [])
        edges = parsed.get("edges", [])
        
        entities_imported = 0
        relationships_imported = 0
        
        # 1. Import Entities (nodes)
        # Keep track of mappings if the canonical names generate new UUIDs
        node_id_map = {}
        for node in nodes:
            name = node.get("name")
            ent_type = node.get("type", "generic")
            desc = node.get("description")
            
            if not name:
                continue
                
            try:
                # add_entity handles duplicate detection automatically
                entity = await self.graph_service.add_entity(
                    name=name,
                    entity_type=ent_type,
                    description=desc,
                    confidence=1.0
                )
                node_id_map[node["id"]] = entity["canonical_name"]
                node_id_map[entity["id"]] = entity["canonical_name"]
                entities_imported += 1
            except Exception as e:
                logger.error(f"Failed to import node {name}: {e}")

        # 2. Import Relationships (edges)
        # Find canonical names from node IDs
        # The exported edges contain 'source' and 'target' which are entity IDs
        for edge in edges:
            src_id = edge.get("source")
            tgt_id = edge.get("target")
            rel_type = edge.get("type")
            conf = edge.get("confidence", 1.0)
            weight = edge.get("weight", 1.0)
            
            if not src_id or not tgt_id or not rel_type:
                continue
                
            src_name = node_id_map.get(src_id)
            tgt_name = node_id_map.get(tgt_id)
            
            if not src_name or not tgt_name:
                continue
                
            try:
                await self.graph_service.add_relationship(
                    source_name=src_name,
                    source_type="generic",
                    target_name=tgt_name,
                    target_type="generic",
                    relation_type=rel_type,
                    confidence=conf,
                    weight=weight
                )
                relationships_imported += 1
            except Exception as e:
                logger.error(f"Failed to import relationship {src_name} -> {tgt_name} ({rel_type}): {e}")

        return {
            "entities_imported": entities_imported,
            "relationships_imported": relationships_imported
        }
