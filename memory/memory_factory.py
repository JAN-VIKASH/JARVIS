"""
Factory for resolving all long-term memory related services and repositories.
"""
import logging
from memory.sqlite_repository import SQLiteMemoryRepository
from memory.chroma_repository import ChromaMemoryRepository
from memory.filter import MemoryFilter
from memory.embedding import EmbeddingService
from memory.scorer import ImportanceScorer
from memory.extractor import MemoryExtractor
from memory.search import MemorySearchService
from memory.memory_service import MemoryService

logger = logging.getLogger("jarvis.memory")

class MemoryFactory:
    """
    Dependency injection factory to resolve components of the memory package.
    Singletons are cached to ensure clean initialization.
    """
    _sqlite_repo = None
    _chroma_repo = None
    _memory_filter = None
    _embedding_service = None
    _scorer = None
    _extractor = None
    _search_service = None
    _conflict_resolver = None
    _decay_service = None
    _memory_service = None
    _adaptive_learner = None

    @classmethod
    def get_adaptive_learner(cls):
        if cls._adaptive_learner is None:
            from memory.scorer import AdaptiveImportanceLearner
            cls._adaptive_learner = AdaptiveImportanceLearner(cls.get_scorer())
        return cls._adaptive_learner

    @classmethod
    def get_sqlite_repo(cls) -> SQLiteMemoryRepository:
        if cls._sqlite_repo is None:
            cls._sqlite_repo = SQLiteMemoryRepository()
        return cls._sqlite_repo

    @classmethod
    def get_chroma_repo(cls) -> ChromaMemoryRepository:
        if cls._chroma_repo is None:
            cls._chroma_repo = ChromaMemoryRepository()
        return cls._chroma_repo

    @classmethod
    def get_memory_filter(cls) -> MemoryFilter:
        if cls._memory_filter is None:
            cls._memory_filter = MemoryFilter()
        return cls._memory_filter

    @classmethod
    def get_embedding_service(cls) -> EmbeddingService:
        if cls._embedding_service is None:
            cls._embedding_service = EmbeddingService()
        return cls._embedding_service

    @classmethod
    def get_scorer(cls) -> ImportanceScorer:
        if cls._scorer is None:
            cls._scorer = ImportanceScorer()
        return cls._scorer

    @classmethod
    def get_extractor(cls) -> MemoryExtractor:
        if cls._extractor is None:
            try:
                from app.services.factory import ServiceFactory
                from memory.llm_extractor import LLMMemoryExtractor
                llm = ServiceFactory.get_llm()
                llm_extractor = LLMMemoryExtractor(llm)
                cls._extractor = MemoryExtractor(llm_extractor=llm_extractor)
            except Exception as e:
                logger.warning(f"Could not load LLMMemoryExtractor for MemoryExtractor (will fall back to Regex): {e}")
                cls._extractor = MemoryExtractor(llm_extractor=None)
        return cls._extractor

    @classmethod
    def get_search_service(cls) -> MemorySearchService:
        if cls._search_service is None:
            cls._search_service = MemorySearchService(
                chroma_repo=cls.get_chroma_repo(),
                sqlite_repo=cls.get_sqlite_repo(),
                embedding_service=cls.get_embedding_service()
            )
        return cls._search_service

    @classmethod
    def get_conflict_resolver(cls):
        if cls._conflict_resolver is None:
            from memory.conflict_resolver import MemoryConflictResolver
            cls._conflict_resolver = MemoryConflictResolver(
                sqlite_repo=cls.get_sqlite_repo(),
                chroma_repo=cls.get_chroma_repo()
            )
        return cls._conflict_resolver

    @classmethod
    def get_decay_service(cls):
        if cls._decay_service is None:
            from memory.decay_service import MemoryDecayService
            cls._decay_service = MemoryDecayService(
                sqlite_repo=cls.get_sqlite_repo(),
                chroma_repo=cls.get_chroma_repo(),
                embedding_service=cls.get_embedding_service()
            )
        return cls._decay_service

    _entity_repo = None
    _relationship_repo = None
    _alias_repo = None
    _user_profile_repo = None
    _alias_engine = None
    _pronoun_resolver = None
    _background_job_manager = None
    _graph_extractor = None
    _graph_service = None
    _user_profile_engine = None

    @classmethod
    def get_entity_repo(cls):
        if cls._entity_repo is None:
            from app.database.repositories.entity_repository import EntityRepository
            cls._entity_repo = EntityRepository()
        return cls._entity_repo

    @classmethod
    def get_relationship_repo(cls):
        if cls._relationship_repo is None:
            from app.database.repositories.relationship_repository import RelationshipRepository
            cls._relationship_repo = RelationshipRepository()
        return cls._relationship_repo

    @classmethod
    def get_alias_repo(cls):
        if cls._alias_repo is None:
            from app.database.repositories.alias_repository import AliasRepository
            cls._alias_repo = AliasRepository()
        return cls._alias_repo

    @classmethod
    def get_user_profile_repo(cls):
        if cls._user_profile_repo is None:
            from app.database.repositories.user_profile_repository import UserProfileRepository
            cls._user_profile_repo = UserProfileRepository()
        return cls._user_profile_repo

    @classmethod
    def get_background_job_manager(cls):
        if cls._background_job_manager is None:
            from app.cognitive.infrastructure.background_job_manager import BackgroundJobManager
            cls._background_job_manager = BackgroundJobManager()
            cls._background_job_manager.start()
        return cls._background_job_manager

    @classmethod
    def get_alias_engine(cls):
        if cls._alias_engine is None:
            from app.cognitive.resolution.alias_resolution_engine import AliasResolutionEngine
            cls._alias_engine = AliasResolutionEngine(
                alias_repo=cls.get_alias_repo(),
                entity_repo=cls.get_entity_repo()
            )
        return cls._alias_engine

    @classmethod
    def get_pronoun_resolver(cls):
        if cls._pronoun_resolver is None:
            from app.cognitive.resolution.pronoun_resolver import PronounResolver
            cls._pronoun_resolver = PronounResolver(entity_repo=cls.get_entity_repo())
        return cls._pronoun_resolver

    @classmethod
    def get_graph_extractor(cls):
        if cls._graph_extractor is None:
            try:
                from app.services.factory import ServiceFactory
                from app.cognitive.knowledge_graph.graph_extractor import GraphExtractor
                llm = ServiceFactory.get_llm()
                cls._graph_extractor = GraphExtractor(llm)
            except Exception as e:
                logger.warning(f"Could not load GraphExtractor: {e}")
                cls._graph_extractor = None
        return cls._graph_extractor

    @classmethod
    def get_graph_service(cls):
        if cls._graph_service is None:
            from app.cognitive.knowledge_graph.knowledge_graph_service import KnowledgeGraphService
            cls._graph_service = KnowledgeGraphService(
                entity_repo=cls.get_entity_repo(),
                relationship_repo=cls.get_relationship_repo(),
                alias_repo=cls.get_alias_repo(),
                alias_engine=cls.get_alias_engine(),
                chroma_repo=cls.get_chroma_repo(),
                embedding_service=cls.get_embedding_service()
            )
        return cls._graph_service

    @classmethod
    def get_user_profile_engine(cls):
        if cls._user_profile_engine is None:
            try:
                from app.services.factory import ServiceFactory
                from app.cognitive.profile.user_profile_engine import UserProfileEngine
                llm = ServiceFactory.get_llm()
                cls._user_profile_engine = UserProfileEngine(
                    profile_repo=cls.get_user_profile_repo(),
                    llm=llm
                )
            except Exception as e:
                logger.warning(f"Could not load UserProfileEngine: {e}")
                cls._user_profile_engine = None
        return cls._user_profile_engine

    @classmethod
    def get_memory_service(cls) -> MemoryService:
        if cls._memory_service is None:
            cls._memory_service = MemoryService(
                sqlite_repo=cls.get_sqlite_repo(),
                chroma_repo=cls.get_chroma_repo(),
                memory_filter=cls.get_memory_filter(),
                embedding_service=cls.get_embedding_service(),
                scorer=cls.get_scorer(),
                extractor=cls.get_extractor(),
                search_service=cls.get_search_service(),
                conflict_resolver=cls.get_conflict_resolver(),
                decay_service=cls.get_decay_service(),
                
                # Phase 5.2 graph DI injects
                graph_extractor=cls.get_graph_extractor(),
                graph_service=cls.get_graph_service(),
                user_profile_engine=cls.get_user_profile_engine(),
                pronoun_resolver=cls.get_pronoun_resolver(),
                background_job_manager=cls.get_background_job_manager()
            )
        return cls._memory_service
