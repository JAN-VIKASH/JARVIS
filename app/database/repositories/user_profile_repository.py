import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, and_
from app.database.session import get_async_session
from app.database.models import UserProfileModel

logger = logging.getLogger("jarvis.database")

class UserProfileRepository:
    """
    Handles SQLite/PostgreSQL database operations for the user_profiles table.
    Enforces Repository Pattern and transactional upsert operations.
    """
    async def get_profile(self, session_id: str, key: str) -> Optional[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(UserProfileModel).where(
                and_(
                    UserProfileModel.session_id == session_id,
                    UserProfileModel.profile_key == key.strip().lower()
                )
            )
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_dict(model) if model else None

    async def update_profile(
        self,
        session_id: str,
        key: str,
        value_dict: Dict[str, Any],
        confidence: float = 1.0,
        source_memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates or updates a key-value record for user profiles, incrementing version numbers.
        """
        async with get_async_session() as session:
            key_norm = key.strip().lower()
            stmt = select(UserProfileModel).where(
                and_(
                    UserProfileModel.session_id == session_id,
                    UserProfileModel.profile_key == key_norm
                )
            )
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            
            if model:
                model.profile_value = json.dumps(value_dict)
                model.confidence = confidence
                model.version += 1
                if source_memory_id:
                    model.source_memory_id = source_memory_id
            else:
                model = UserProfileModel(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    profile_key=key_norm,
                    profile_value=json.dumps(value_dict),
                    confidence=confidence,
                    version=1,
                    source_memory_id=source_memory_id
                )
                session.add(model)
                
            await session.commit()
            await session.refresh(model)
            return self._to_dict(model)

    async def delete_profile(self, session_id: str, key: str) -> bool:
        async with get_async_session() as session:
            stmt = delete(UserProfileModel).where(
                and_(
                    UserProfileModel.session_id == session_id,
                    UserProfileModel.profile_key == key.strip().lower()
                )
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def list_profiles(self, session_id: str) -> List[Dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(UserProfileModel).where(UserProfileModel.session_id == session_id)
            res = await session.execute(stmt)
            models = res.scalars().all()
            return [self._to_dict(m) for m in models]

    def _to_dict(self, model: UserProfileModel) -> Dict[str, Any]:
        try:
            val = json.loads(model.profile_value)
        except Exception:
            val = {"value": model.profile_value}
            
        return {
            "id": model.id,
            "session_id": model.session_id,
            "profile_key": model.profile_key,
            "profile_value": val,
            "confidence": model.confidence,
            "version": model.version,
            "source_memory_id": model.source_memory_id,
            "updated_at": model.updated_at
        }
