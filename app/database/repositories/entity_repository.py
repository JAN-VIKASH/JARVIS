import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, update, and_, or_, func
from app.database.session import get_async_session
from app.database.models import EntityModel, AliasModel, RelationshipModel, EntityMergeAuditModel

logger = logging.getLogger("jarvis.database")

class EntityRepository:
    """
    Handles SQLite/PostgreSQL database operations for the entities table.
    Enforces Repository Pattern, transactions, and copy-on-write versioning.
    """
    async def create_entity(
        self,
        canonical_name: str,
        entity_type: str,
        description: Optional[str] = None,
        confidence: float = 1.0,
        embedding_id: Optional[str] = None,
        metadata_json: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            model = EntityModel(
                id=str(uuid.uuid4()),
                canonical_name=canonical_name,
                normalized_name=canonical_name.strip().lower(),
                entity_type=entity_type.strip().lower(),
                description=description,
                confidence=confidence,
                embedding_id=embedding_id,
                metadata_json=metadata_json,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                mention_count=1,
                version=1
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(EntityModel).where(EntityModel.id == entity_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def get_by_name(self, name: str, entity_type: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(EntityModel).where(
                and_(
                    EntityModel.normalized_name == name.strip().lower(),
                    EntityModel.entity_type == entity_type.strip().lower()
                )
            )
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def update_entity(
        self,
        entity_id: str,
        canonical_name: Optional[str] = None,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
        embedding_id: Optional[str] = None,
        metadata_json: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Implements versioned entity updates (copy-on-write version tracking for audits).
        """
        async with get_async_session() as session:
            stmt = select(EntityModel).where(EntityModel.id == entity_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if not model:
                raise ValueError(f"Entity {entity_id} not found")
                
            model.version += 1
            if canonical_name:
                model.canonical_name = canonical_name
                model.normalized_name = canonical_name.strip().lower()
            if description:
                model.description = description
            if confidence is not None:
                model.confidence = confidence
            if embedding_id:
                model.embedding_id = embedding_id
            if metadata_json:
                model.metadata_json = metadata_json
                
            model.last_seen = datetime.utcnow()
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def increment_mentions(self, entity_id: str) -> None:
        async with get_async_session() as session:
            stmt = select(EntityModel).where(EntityModel.id == entity_id)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if model:
                model.mention_count += 1
                model.last_seen = datetime.utcnow()
                await session.commit()

    async def delete_entity(self, entity_id: str) -> bool:
        async with get_async_session() as session:
            stmt = delete(EntityModel).where(EntityModel.id == entity_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def list_entities(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(EntityModel).order_by(EntityModel.canonical_name.asc()).limit(limit).offset(offset)
            res = await session.execute(stmt)
            models = res.scalars().all()
            return [self._to_dict(m) for m in models]

    async def search_entities(self, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            norm = query_text.strip().lower()
            stmt = select(EntityModel).where(
                or_(
                    EntityModel.normalized_name.contains(norm),
                    EntityModel.description.contains(norm)
                )
            ).limit(limit)
            res = await session.execute(stmt)
            models = res.scalars().all()
            return [self._to_dict(m) for m in models]

    async def merge_entities(self, primary_id: str, duplicate_id: str) -> Dict[str, Any]:
        """
        Merges duplicate entity node into primary entity node under a single atomic transaction.
        Rewires connected relationships, re-assigns aliases, updates mentions/timestamps,
        logs merge audit trail, and deletes the duplicate entity.
        """
        async with get_async_session() as session:
            # Re-fetch models inside session to execute transaction mutations
            prim_stmt = select(EntityModel).where(EntityModel.id == primary_id)
            dup_stmt = select(EntityModel).where(EntityModel.id == duplicate_id)
            
            p_res = await session.execute(prim_stmt)
            d_res = await session.execute(dup_stmt)
            
            primary = p_res.scalar_one_or_none()
            duplicate = d_res.scalar_one_or_none()
            
            if not primary or not duplicate:
                raise ValueError("Both primary and duplicate entities must exist to merge.")

            # Update primary metrics
            primary.mention_count += duplicate.mention_count
            primary.last_seen = max(primary.last_seen, duplicate.last_seen)
            if not primary.description and duplicate.description:
                primary.description = duplicate.description
            elif primary.description and duplicate.description and duplicate.description not in primary.description:
                primary.description += f" / {duplicate.description}"
                
            # Log merge audit
            audit = EntityMergeAuditModel(
                id=str(uuid.uuid4()),
                source_entity_id=duplicate_id,
                target_entity_id=primary_id,
                merge_metadata=f"Merged '{duplicate.canonical_name}' ({duplicate.entity_type}) into '{primary.canonical_name}' ({primary.entity_type})."
            )
            session.add(audit)

            # Move aliases
            alias_stmt = select(AliasModel).where(AliasModel.entity_id == duplicate_id)
            aliases_res = await session.execute(alias_stmt)
            aliases = aliases_res.scalars().all()
            for al in aliases:
                # Re-assign or delete if primary already has it
                check_stmt = select(AliasModel).where(
                    and_(
                        AliasModel.entity_id == primary_id,
                        AliasModel.normalized_alias == al.normalized_alias
                    )
                )
                c_res = await session.execute(check_stmt)
                if c_res.scalar_one_or_none():
                    await session.delete(al)
                else:
                    al.entity_id = primary_id

            # Move relationships
            rel_stmt = select(RelationshipModel).where(
                or_(
                    RelationshipModel.source_entity_id == duplicate_id,
                    RelationshipModel.target_entity_id == duplicate_id
                )
            )
            rels_res = await session.execute(rel_stmt)
            relationships = rels_res.scalars().all()
            
            for rel in relationships:
                # Rewire endpoints
                new_source = primary_id if rel.source_entity_id == duplicate_id else rel.source_entity_id
                new_target = primary_id if rel.target_entity_id == duplicate_id else rel.target_entity_id
                
                if new_source == new_target:
                    # Self-loop generated by merge, delete it
                    await session.delete(rel)
                    continue

                # Check if relationship already exists between primary and endpoint
                check_stmt = select(RelationshipModel).where(
                    and_(
                        RelationshipModel.source_entity_id == new_source,
                        RelationshipModel.target_entity_id == new_target,
                        RelationshipModel.relation_type == rel.relation_type
                    )
                )
                c_res = await session.execute(check_stmt)
                existing_rel = c_res.scalar_one_or_none()
                if existing_rel:
                    # Merge weight and confidence, then delete duplicate relationship
                    existing_rel.weight = max(existing_rel.weight, rel.weight)
                    existing_rel.confidence = max(existing_rel.confidence, rel.confidence)
                    await session.delete(rel)
                else:
                    rel.source_entity_id = new_source
                    rel.target_entity_id = new_target
            
            # Delete duplicate node
            await session.delete(duplicate)
            await session.commit()
            await session.refresh(primary)
            return self._to_dict(primary)

    def _to_dict(self, model: EntityModel) -> Dict[str, Any]:
        return {
            "id": model.id,
            "canonical_name": model.canonical_name,
            "normalized_name": model.normalized_name,
            "entity_type": model.entity_type,
            "description": model.description,
            "confidence": model.confidence,
            "embedding_id": model.embedding_id,
            "metadata_json": model.metadata_json,
            "first_seen": model.first_seen,
            "last_seen": model.last_seen,
            "mention_count": model.mention_count,
            "version": model.version,
            "created_at": model.created_at,
            "updated_at": model.updated_at
        }
