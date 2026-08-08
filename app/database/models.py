"""
SQLAlchemy ORM models for Long-Term Memory storage.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, func, ForeignKey, UniqueConstraint
from app.database.base import Base

class ConversationModel(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)

class UserFactModel(Base):
    __tablename__ = "user_facts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False, index=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    importance = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Metadata tracking columns
    last_accessed_at = Column(DateTime, default=func.now(), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class PreferenceModel(Base):
    __tablename__ = "preferences"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False, index=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    importance = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Metadata tracking columns
    last_accessed_at = Column(DateTime, default=func.now(), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class GoalModel(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False)
    importance = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Metadata tracking columns
    last_accessed_at = Column(DateTime, default=func.now(), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class TaskModel(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), default="default", nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    due_date = Column(DateTime, nullable=True)
    importance = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Metadata tracking columns
    last_accessed_at = Column(DateTime, default=func.now(), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class NoteModel(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    importance = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Metadata tracking columns
    last_accessed_at = Column(DateTime, default=func.now(), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class MemoryMetadataModel(Base):
    __tablename__ = "memory_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(50), nullable=False, index=True)  # conversation, fact, preference, goal, task, note
    record_id = Column(Integer, nullable=False)
    chroma_id = Column(String(100), nullable=False, unique=True, index=True)
    importance = Column(Integer, default=50, nullable=False)
    last_indexed = Column(DateTime, default=func.now(), nullable=False)
    
    # New columns for retry and version mapping
    embedding_model = Column(String(100), nullable=True)
    pending_index = Column(Boolean, default=False, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    last_retry_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="active", nullable=False)  # "active", "pending", "failed"


class EventMemoryModel(Base):
    __tablename__ = "event_memories"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=True)  # e.g., meeting, milestone, deadline, task
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    is_all_day = Column(Boolean, default=False, nullable=False)
    raw_text = Column(Text, nullable=True)
    status = Column(String(20), default="planned", nullable=False)  # planned, completed, cancelled, postponed
    importance = Column(String(20), default="medium", nullable=False)  # low, medium, high
    confidence = Column(Float, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    parent_event_id = Column(String(36), nullable=True)
    embedding_id = Column(String(255), nullable=True)
    
    # Recurrence columns for Phase 5.3
    recurrence_rule = Column(String(50), nullable=True)
    recurrence_until = Column(DateTime, nullable=True)
    recurrence_series_id = Column(String(36), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class EntityModel(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("normalized_name", "entity_type", name="uq_entity_name_type"),
    )
    
    id = Column(String(36), primary_key=True)
    canonical_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    embedding_id = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=True)  # extensible JSON attributes
    first_seen = Column(DateTime, default=func.now(), nullable=False)
    last_seen = Column(DateTime, default=func.now(), nullable=False)
    mention_count = Column(Integer, default=1, nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class AliasModel(Base):
    __tablename__ = "entity_aliases"
    
    id = Column(String(36), primary_key=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(255), nullable=False)
    normalized_alias = Column(String(255), nullable=False, unique=True)
    confidence = Column(Float, default=1.0, nullable=False)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class RelationshipModel(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("source_entity_id", "target_entity_id", "relation_type", name="uq_rel_source_target_type"),
    )
    
    id = Column(String(36), primary_key=True)
    source_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, default=1.0, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    bidirectional = Column(Boolean, default=False, nullable=False)
    evidence_memory_id = Column(String(100), nullable=True)
    source_session_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class UserProfileModel(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("session_id", "profile_key", name="uq_session_profile_key"),
    )
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(50), nullable=False, index=True)
    profile_key = Column(String(100), nullable=False)
    profile_value = Column(Text, nullable=False)  # JSON-serialized
    confidence = Column(Float, default=1.0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    source_memory_id = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class EntityMergeAuditModel(Base):
    __tablename__ = "entity_merge_audits"
    
    id = Column(String(36), primary_key=True)
    source_entity_id = Column(String(36), nullable=False)
    target_entity_id = Column(String(36), nullable=False)
    merge_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

