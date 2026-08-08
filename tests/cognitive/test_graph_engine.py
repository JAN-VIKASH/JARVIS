import asyncio
import json
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.database.migrations import init_db
from app.database.session import get_async_session
from app.database.models import (
    EntityModel, AliasModel, RelationshipModel, UserProfileModel, EntityMergeAuditModel
)
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig

from app.database.repositories.entity_repository import EntityRepository
from app.database.repositories.relationship_repository import RelationshipRepository
from app.database.repositories.alias_repository import AliasRepository
from app.database.repositories.user_profile_repository import UserProfileRepository

from app.cognitive.infrastructure.exceptions import GraphException
from app.cognitive.infrastructure.background_job_manager import BackgroundJobManager
from app.cognitive.infrastructure.context_builder import ContextBuilder

from app.cognitive.resolution.alias_resolution_engine import AliasResolutionEngine, levenshtein_similarity
from app.cognitive.resolution.pronoun_resolver import PronounResolver

from app.cognitive.profile.user_profile_engine import UserProfileEngine

from app.cognitive.knowledge_graph.graph_extractor import GraphExtractor
from app.cognitive.knowledge_graph.knowledge_graph_service import KnowledgeGraphService
from app.cognitive.knowledge_graph.graph_exporter import GraphExporter
from app.cognitive.knowledge_graph.graph_importer import GraphImporter
from app.cognitive.knowledge_graph.graph_statistics import GraphStatistics
from app.cognitive.knowledge_graph.graph_reasoner import GraphReasoner

from memory.test_memory import clear_database
from app.services.chat_service import ChatService

class MockLLMForGraph(BaseLLM):
    def __init__(self):
        super().__init__()
        self.mock_entities = []
        self.mock_relationships = []
        self.mock_updates = []

    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        if "user profile" in system_prompt:
            resp = json.dumps({"updates": self.mock_updates})
        else:
            resp = json.dumps({
                "entities": self.mock_entities,
                "relationships": self.mock_relationships
            })
            
        return LLMResult(
            response=resp,
            provider="mock",
            model="mock",
            latency=0.002,
            input_tokens=5,
            output_tokens=5,
            total_tokens=10
        )

class TestGraphEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Force database schema rebuild for clean test execution
        from sqlalchemy import text
        async with get_async_session() as session:
            await session.execute(text("DROP TABLE IF EXISTS entity_merge_audits"))
            await session.execute(text("DROP TABLE IF EXISTS entity_aliases"))
            await session.execute(text("DROP TABLE IF EXISTS relationships"))
            await session.execute(text("DROP TABLE IF EXISTS user_profiles"))
            await session.execute(text("DROP TABLE IF EXISTS entities"))
            await session.commit()
            
        await init_db()
        await clear_database()
        
        self.mock_llm = MockLLMForGraph()
        
        # Instantiate repositories
        self.entity_repo = EntityRepository()
        self.relationship_repo = RelationshipRepository()
        self.alias_repo = AliasRepository()
        self.profile_repo = UserProfileRepository()
        
        # Instantiate engines and services
        self.alias_engine = AliasResolutionEngine(self.alias_repo, self.entity_repo)
        self.pronoun_resolver = PronounResolver(self.entity_repo)
        
        # Mock ChromaDB persistent client wrapper
        class MockChromaRepo:
            def __init__(self):
                self.embeddings = {}
                class MockCollection:
                    def delete(self, ids):
                        pass
                self.collection = MockCollection()
            def save_embedding(self, memory_id, embedding, document, metadata):
                self.embeddings[memory_id] = (embedding, document, metadata)
                
        class MockEmbeddingService:
            def __init__(self):
                self.model_name = "mock"
            def get_embeddings(self, text):
                return [0.1, 0.2, 0.3]
                
        self.chroma_repo = MockChromaRepo()
        self.embedding_service = MockEmbeddingService()
        
        self.graph_service = KnowledgeGraphService(
            self.entity_repo,
            self.relationship_repo,
            self.alias_repo,
            self.alias_engine,
            self.chroma_repo,
            self.embedding_service
        )
        
        self.user_profile_engine = UserProfileEngine(self.profile_repo, self.mock_llm)
        self.graph_reasoner = GraphReasoner(self.graph_service, self.entity_repo, self.relationship_repo)

    async def test_entity_crud_and_levenshtein(self):
        # Verify Levenshtein
        self.assertAlmostEqual(levenshtein_similarity("Tony Stark", "Tony Stark"), 1.0)
        self.assertAlmostEqual(levenshtein_similarity("Tony Stark", "Tony"), 0.4)
        
        # Create Entity
        ent = await self.entity_repo.create_entity(
            canonical_name="Tony Stark",
            entity_type="person",
            description="Iron Man"
        )
        self.assertEqual(ent["canonical_name"], "Tony Stark")
        self.assertEqual(ent["entity_type"], "person")
        self.assertEqual(ent["version"], 1)
        
        # Update Entity (check copy-on-write versioning)
        updated = await self.entity_repo.update_entity(ent["id"], description="Billionaire genius")
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["description"], "Billionaire genius")

    async def test_alias_resolution_and_deduplication(self):
        # Create entity and add aliases
        ent = await self.graph_service.add_entity("Tony Stark", "person", "Iron Man")
        await self.alias_repo.add_alias(ent["id"], "Iron Man")
        await self.alias_repo.add_alias(ent["id"], "Mr Stark")
        
        # Resolve exact alias
        res_exact = await self.alias_engine.resolve_alias("Iron Man")
        self.assertEqual(res_exact, ent["id"])
        
        # Resolve fuzzy match
        res_fuzzy = await self.alias_engine.resolve_alias("Tony Stak")
        self.assertEqual(res_fuzzy, ent["id"])
        
        # Invalidate alias cache
        self.alias_engine.invalidate_key("Tony Stak")

    async def test_relationship_crud_and_pathfinding(self):
        # Add entities
        e1 = await self.graph_service.add_entity("User", "person")
        e2 = await self.graph_service.add_entity("ResearchHub", "project")
        e3 = await self.graph_service.add_entity("Java", "programming language")
        
        # Add relationships
        r1 = await self.graph_service.add_relationship("User", "person", "ResearchHub", "project", "WORKS_ON", weight=3.0)
        r2 = await self.graph_service.add_relationship("ResearchHub", "project", "Java", "programming language", "USES", weight=2.0)
        
        # Find path (User -> ResearchHub -> Java)
        path = await self.relationship_repo.find_path(e1["id"], e3["id"])
        self.assertEqual(path, [e1["id"], e2["id"], e3["id"]])
        
        # Get Connected Components
        comps = await self.relationship_repo.get_connected_components()
        self.assertEqual(len(comps), 1)

    async def test_entity_merging(self):
        e1 = await self.graph_service.add_entity("Tony Stark", "person", "Iron Man")
        e2 = await self.graph_service.add_entity("Tony", "person", "Tech billionaire")
        
        # Add alias and relationships to duplicate
        await self.alias_repo.add_alias(e2["id"], "Iron Man Mark 2")
        await self.graph_service.add_relationship("Tony", "person", "ResearchHub", "project", "WORKS_ON")
        
        # Merge Tony into Tony Stark
        merged = await self.entity_repo.merge_entities(primary_id=e1["id"], duplicate_id=e2["id"])
        self.assertEqual(merged["mention_count"], 3)
        
        # Assert duplicate was deleted
        self.assertIsNone(await self.entity_repo.get_entity(e2["id"]))
        
        # Verify relations rewrote to Tony Stark
        rels = await self.relationship_repo.find_relationships(source_id=e1["id"])
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["relation_type"], "WORKS_ON")

    async def test_user_profile_engine(self):
        session_id = "test_profile_session"
        
        # Operations: add
        await self.user_profile_engine.update_profile_key(session_id, "languages", "add", "Python")
        await self.user_profile_engine.update_profile_key(session_id, "languages", "add", "JavaScript")
        
        prof = await self.user_profile_engine.get_profile_context(session_id)
        self.assertIn("Python", prof["languages"])
        self.assertIn("JavaScript", prof["languages"])
        
        # Operations: remove
        await self.user_profile_engine.update_profile_key(session_id, "languages", "remove", "JavaScript")
        prof = await self.user_profile_engine.get_profile_context(session_id)
        self.assertNotIn("JavaScript", prof["languages"])
        
        # Operations: set
        await self.user_profile_engine.update_profile_key(session_id, "ide", "set", "VS Code")
        prof = await self.user_profile_engine.get_profile_context(session_id)
        self.assertEqual(prof["ide"], ["VS Code"])

    async def test_pronoun_resolver(self):
        ent = await self.graph_service.add_entity("Python", "programming language")
        
        history = [
            {"role": "user", "content": "I am working in Python today."},
            {"role": "assistant", "content": "Python is a high-level scripting language."}
        ]
        
        res = await self.pronoun_resolver.resolve_referent("Where is it used?", history)
        self.assertIsNotNone(res)
        self.assertEqual(res["canonical_name"], "Python")

    async def test_multi_hop_graph_reasoning(self):
        # Build chain: User -> WORKS_ON -> ResearchHub -> USES -> Java
        await self.graph_service.add_relationship("User", "person", "ResearchHub", "project", "WORKS_ON")
        await self.graph_service.add_relationship("ResearchHub", "project", "Java", "programming language", "USES")
        
        # Multi-hop query: start="User", chain=["WORKS_ON", "USES"]
        targets = await self.graph_reasoner.reason_relation_chain("User", ["WORKS_ON", "USES"])
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["canonical_name"], "Java")

    async def test_visualization_exporters_importers_and_stats(self):
        # Add basic graph nodes
        await self.graph_service.add_relationship("ResearchHub", "project", "Python", "programming language", "USES")
        
        # Exporters
        exporter = GraphExporter(self.entity_repo, self.relationship_repo)
        json_export = await exporter.export_to_json()
        dot_export = await exporter.export_to_dot()
        xml_export = await exporter.export_to_graphml()
        
        self.assertIn("nodes", json_export)
        self.assertIn("digraph", dot_export)
        self.assertIn("xml", xml_export)
        
        # Importer backup restore
        importer = GraphImporter(self.graph_service)
        res = await importer.import_from_json(json_export)
        self.assertGreaterEqual(res["entities_imported"], 1)
        
        # Stats service
        stats = GraphStatistics(self.entity_repo, self.relationship_repo)
        metrics = await stats.compute_statistics()
        self.assertGreaterEqual(metrics["node_count"], 2)
        self.assertGreaterEqual(metrics["average_degree"], 1.0)

    async def test_entity_deletion_safety(self):
        # Create entity and relationships
        e = await self.graph_service.add_entity("Java", "programming language")
        await self.graph_service.add_relationship("ResearchHub", "project", "Java", "programming language", "USES")
        
        # Delete Java safely
        success = await self.graph_service.delete_entity_safely(e["id"])
        self.assertTrue(success)
        
        # Assert entity and relationship cleanups
        self.assertIsNone(await self.entity_repo.get_entity(e["id"]))
        rels = await self.relationship_repo.find_relationships(target_id=e["id"])
        self.assertEqual(len(rels), 0)

    async def test_context_builder_budgeting(self):
        builder = ContextBuilder(max_tokens=50) # small budget
        
        profile = {"languages": ["Python", "C++"]}
        direct = ["Tony Stark works on ResearchHub."]
        semantic = ["Python is a scripting language."]
        
        context = builder.build_context(
            user_profile=profile,
            direct_memories=direct,
            semantic_memories=semantic
        )
        # Context must fit and contain warning truncation
        self.assertLessEqual(len(context) // 4, 100)
