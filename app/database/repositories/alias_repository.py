import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, and_
from app.database.session import get_async_session
from app.database.models import AliasModel

logger = logging.getLogger("jarvis.database")

class AliasRepository:
    """
    Handles SQLite/PostgreSQL database operations for the entity_aliases table.
    Enforces Repository Pattern and case-insensitive unique constraints.
    """
    async def add_alias(
        self,
        entity_id: str,
        alias: str,
        confidence: float = 1.0,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        async with get_async_session() as session:
            norm_alias = alias.strip().lower()
            
            # Check if this exact normalized alias already exists to prevent duplication
            stmt = select(AliasModel).where(AliasModel.normalized_alias == norm_alias)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if model:
                # If it already points to the same entity, return it. Otherwise, raise conflict
                if model.entity_id == entity_id:
                    return self._to_dict(model)
                raise ValueError(f"Alias '{alias}' is already registered to entity {model.entity_id}")
                
            model = AliasModel(
                id=str(uuid.uuid4()),
                entity_id=entity_id,
                alias=alias.strip(),
                normalized_alias=norm_alias,
                confidence=confidence,
                source=source
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def remove_alias(self, alias_id: str) -> bool:
        async with get_async_session() as session:
            stmt = delete(AliasModel).where(AliasModel.id == alias_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def find_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(AliasModel).where(AliasModel.normalized_alias == alias.strip().lower())
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def list_aliases(self, entity_id: str) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(AliasModel).where(AliasModel.entity_id == entity_id)
            res = await session.execute(stmt)
            models = res.scalars().all()
            return [self._to_dict(m) for m in models]

    def _to_dict(self, model: AliasModel) -> Dict[str, Any]:
        return {
            "id": model.id,
            "entity_id": model.entity_id,
            "alias": model.alias,
            "normalized_alias": model.normalized_alias,
            "confidence": model.confidence,
            "source": model.source,
            "created_at": model.created_at
        }
