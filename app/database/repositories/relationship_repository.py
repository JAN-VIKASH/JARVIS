import uuid
import logging
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import select, delete, and_, or_
from app.database.session import get_async_session
from app.database.models import RelationshipModel, EntityModel

logger = logging.getLogger("jarvis.database")

class RelationshipRepository:
    """
    Handles SQLite/PostgreSQL database operations for the relationships table.
    Enforces Repository Pattern, neighborhood searches, and pathfinding queries.
    """
    async def create_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        confidence: float = 1.0,
        weight: float = 1.0,
        bidirectional: bool = False,
        evidence_memory_id: Optional[str] = None,
        source_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            model = RelationshipModel(
                id=str(uuid.uuid4()),
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                relation_type=relation_type.strip().upper(),
                confidence=confidence,
                weight=weight,
                bidirectional=bidirectional,
                evidence_memory_id=evidence_memory_id,
                source_session_id=source_session_id
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def get_relationship(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(RelationshipModel).where(RelationshipModel.id == relationship_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def relationship_exists(
        self,
        source_id: str,
        target_id: str,
        relation_type: str
    ) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(RelationshipModel).where(
                and_(
                    RelationshipModel.source_entity_id == source_id,
                    RelationshipModel.target_entity_id == target_id,
                    RelationshipModel.relation_type == relation_type.strip().upper()
                )
            )
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def update_relationship(
        self,
        relationship_id: str,
        confidence: Optional[float] = None,
        weight: Optional[float] = None,
        evidence_memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            stmt = select(RelationshipModel).where(RelationshipModel.id == relationship_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if not model:
                raise ValueError(f"Relationship {relationship_id} not found")
                
            if confidence is not None:
                model.confidence = confidence
            if weight is not None:
                model.weight = weight
            if evidence_memory_id:
                model.evidence_memory_id = evidence_memory_id
                
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def delete_relationship(self, relationship_id: str) -> bool:
        async with get_async_session() as session:
            stmt = delete(RelationshipModel).where(RelationshipModel.id == relationship_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def find_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        rel_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            filters = []
            if source_id:
                filters.append(RelationshipModel.source_entity_id == source_id)
            if target_id:
                filters.append(RelationshipModel.target_entity_id == target_id)
            if rel_type:
                filters.append(RelationshipModel.relation_type == rel_type.strip().upper())
                
            stmt = select(RelationshipModel)
            if filters:
                stmt = stmt.where(and_(*filters))
                
            res = await session.execute(stmt)
            models = res.scalars().all()
            return [self._to_dict(m) for m in models]

    async def find_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves direct one-hop neighbor nodes along with the connecting relationships.
        """
        async with get_async_session() as session:
            stmt = select(RelationshipModel).where(
                or_(
                    RelationshipModel.source_entity_id == entity_id,
                    RelationshipModel.target_entity_id == entity_id
                )
            )
            res = await session.execute(stmt)
            rels = res.scalars().all()
            
            neighbors = []
            for r in rels:
                neighbor_id = r.target_entity_id if r.source_entity_id == entity_id else r.source_entity_id
                neighbors.append({
                    "relationship_id": r.id,
                    "entity_id": neighbor_id,
                    "relation_type": r.relation_type,
                    "confidence": r.confidence,
                    "weight": r.weight,
                    "direction": "out" if r.source_entity_id == entity_id else "in"
                })
            return neighbors

    async def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> Optional[List[str]]:
        """
        BFS path finding to discover the shortest hop chain between source and target entities.
        Includes safety depth guards and visited loop checks.
        """
        if source_id == target_id:
            return [source_id]
            
        queue = [[source_id]]
        visited = {source_id}
        
        while queue:
            path = queue.pop(0)
            node = path[-1]
            
            if len(path) > max_depth + 1:
                continue
                
            if node == target_id:
                return path
                
            neighbors = await self.find_neighbors(node)
            for neighbor in neighbors:
                neighbor_id = neighbor["entity_id"]
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    new_path = list(path)
                    new_path.append(neighbor_id)
                    queue.append(new_path)
                    
        return None

    async def get_connected_components(self) -> List[List[str]]:
        """
        Identifies connected components/clusters of entities in the database.
        """
        async with get_async_session() as session:
            # Get all entities
            stmt = select(EntityModel.id)
            res = await session.execute(stmt)
            all_node_ids = [row[0] for row in res.all()]
            
            components = []
            visited = set()
            
            for node_id in all_node_ids:
                if node_id not in visited:
                    # BFS to find component
                    comp = []
                    queue = [node_id]
                    visited.add(node_id)
                    
                    while queue:
                        curr = queue.pop(0)
                        comp.append(curr)
                        
                        neighbors = await self.find_neighbors(curr)
                        for n in neighbors:
                            n_id = n["entity_id"]
                            if n_id not in visited:
                                visited.add(n_id)
                                queue.append(n_id)
                                
                    components.append(comp)
            return components

    def _to_dict(self, model: RelationshipModel) -> Dict[str, Any]:
        return {
            "id": model.id,
            "source_entity_id": model.source_entity_id,
            "target_entity_id": model.target_entity_id,
            "relation_type": model.relation_type,
            "confidence": model.confidence,
            "weight": model.weight,
            "bidirectional": model.bidirectional,
            "evidence_memory_id": model.evidence_memory_id,
            "source_session_id": model.source_session_id,
            "created_at": model.created_at,
            "updated_at": model.updated_at
        }
