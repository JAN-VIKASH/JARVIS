import json
from typing import Dict, Any, List
from app.database.repositories.entity_repository import EntityRepository
from app.database.repositories.relationship_repository import RelationshipRepository

class GraphExporter:
    """
    Exposes graph serialization templates converting the SQL-based knowledge graph state
    to JSON, GraphML, or DOT (Graphviz) visualization payloads.
    """
    def __init__(self, entity_repo: EntityRepository, relationship_repo: RelationshipRepository):
        self.entity_repo = entity_repo
        self.relationship_repo = relationship_repo

    async def export_to_json(self) -> str:
        """
        Exports the graph to standard Node/Edge JSON layout.
        """
        entities = await self.entity_repo.list_entities(limit=1000)
        relationships = await self.relationship_repo.find_relationships()
        
        nodes = []
        for ent in entities:
            nodes.append({
                "id": ent["id"],
                "name": ent["canonical_name"],
                "type": ent["entity_type"],
                "description": ent["description"],
                "mention_count": ent["mention_count"]
            })
            
        edges = []
        for r in relationships:
            edges.append({
                "id": r["id"],
                "source": r["source_entity_id"],
                "target": r["target_entity_id"],
                "type": r["relation_type"],
                "confidence": r["confidence"],
                "weight": r["weight"]
            })
            
        return json.dumps({"nodes": nodes, "edges": edges}, indent=2)

    async def export_to_dot(self) -> str:
        """
        Exports the graph to Graphviz DOT layout.
        """
        entities = await self.entity_repo.list_entities(limit=1000)
        relationships = await self.relationship_repo.find_relationships()
        
        # Build node id map
        node_names = {ent["id"]: ent["canonical_name"] for ent in entities}
        
        lines = ["digraph JARVIS_Knowledge_Graph {", '  node [shape=box, style="filled,rounded", color="#1a73e8", fontcolor=white];']
        
        # Add nodes
        for ent_id, name in node_names.items():
            # escape double quotes
            safe_name = name.replace('"', '\\"')
            lines.append(f'  "{ent_id}" [label="{safe_name}"];')
            
        # Add edges
        for r in relationships:
            src = r["source_entity_id"]
            tgt = r["target_entity_id"]
            if src in node_names and tgt in node_names:
                label = r["relation_type"]
                lines.append(f'  "{src}" -> "{tgt}" [label="{label}", weight={r["weight"]}];')
                
        lines.append("}")
        return "\n".join(lines)

    async def export_to_graphml(self) -> str:
        """
        Exports the graph to XML GraphML layout.
        """
        entities = await self.entity_repo.list_entities(limit=1000)
        relationships = await self.relationship_repo.find_relationships()
        
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
            '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
            '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
            '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <graph id="G" edgedefault="directed">'
        ]
        
        for ent in entities:
            safe_name = ent["canonical_name"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f'    <node id="{ent["id"]}">')
            lines.append(f'      <data key="name">{safe_name}</data>')
            lines.append(f'      <data key="type">{ent["entity_type"]}</data>')
            lines.append('    </node>')
            
        for r in relationships:
            lines.append(f'    <edge source="{r["source_entity_id"]}" target="{r["target_entity_id"]}">')
            lines.append(f'      <data key="relation">{r["relation_type"]}</data>')
            lines.append(f'      <data key="weight">{r["weight"]}</data>')
            lines.append('    </edge>')
            
        lines.append('  </graph>')
        lines.append('</graphml>')
        return "\n".join(lines)
