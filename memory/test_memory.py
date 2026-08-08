"""
Expanded validation runner to test Phase 4.1 advanced memory features:
Hybrid Extraction, Versioning, Decay/Aging, Concurrency optimistic locks, Soft Deletes, and Index Retries.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from app.database.migrations import init_db
from sqlalchemy import select
from app.database.session import get_async_session
from app.database.models import UserFactModel, PreferenceModel, GoalModel, TaskModel, NoteModel, MemoryMetadataModel
from memory.memory_factory import MemoryFactory
from memory.filter import MemoryFilter
from memory.extractor import MemoryExtractor
from memory.scorer import ImportanceScorer
from memory.llm_extractor import LLMMemoryExtractor

# Setup test logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_memory")

async def clear_database():
    """Wipes the database tables for clean test executions."""
    async with get_async_session() as session:
        for model in [UserFactModel, PreferenceModel, GoalModel, TaskModel, NoteModel, MemoryMetadataModel]:
            await session.execute(model.__table__.delete())
        await session.flush()

async def test_memory_filter():
    print("\n--- Testing Memory Filter ---")
    filt = MemoryFilter()
    
    assert filt.should_persist("Hello JARVIS!") is False
    assert filt.should_persist("My name is Tony Stark.") is True
    print("Memory Filter tests PASSED.")

async def test_hybrid_extraction():
    print("\n--- Testing Hybrid Extraction & Fallback ---")
    ext = MemoryExtractor()
    scorer = ImportanceScorer()
    
    # 1. Test standard regex match
    res_regex = await ext.extract("My name is Tony Stark.")
    assert len(res_regex) > 0
    assert res_regex[0]["key"] == "name"
    assert res_regex[0]["value"] == "Tony Stark"
    
    # 2. Test LLM extractor fallback mock
    class MockLLMExtractor(LLMMemoryExtractor):
        def __init__(self):
            pass
        async def extract(self, text: str):
            return [{
                "type": "preference",
                "category": "likes",
                "key": "liked_ide",
                "value": "VS Code",
                "confidence": 0.85
            }]
            
    mock_llm = MockLLMExtractor()
    hybrid_ext = MemoryExtractor(llm_extractor=mock_llm)
    
    # Text that regex fails to extract, but has memory indicators
    res_hybrid = await hybrid_ext.extract("I really prefer working in VS Code for projects.")
    assert len(res_hybrid) > 0
    assert res_hybrid[0]["key"] == "liked_ide"
    assert res_hybrid[0]["value"] == "VS Code"
    
    print("Hybrid Extraction tests PASSED.")

async def test_conflict_resolution_and_versioning():
    print("\n--- Testing Conflict Resolution & Versioning ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    
    # 1. Single-value attribute versioning (Facts/Preferences name/favourite_language)
    print("Saving name: 'My name is Tony Stark.'")
    await memory_service._async_extract_and_save("My name is Tony Stark.")
    
    # Verify version 1
    facts = await memory_service.sqlite_repo.search_facts("name")
    assert len(facts) == 1
    assert facts[0]["value"] == "Tony Stark"
    assert facts[0]["version"] == 1
    assert facts[0]["is_active"] is True
    
    # Update single-value attribute
    print("Updating name: 'My name is Iron Man.'")
    await memory_service._async_extract_and_save("My name is Iron Man.")
    
    # Verify versioning: one active version 2, and one inactive version 1
    async with get_async_session() as session:
        from sqlalchemy import select
        res = await session.execute(select(UserFactModel).order_by(UserFactModel.version.asc()))
        all_versions = res.scalars().all()
        assert len(all_versions) == 2
        
        # Version 1 is deactivated
        assert all_versions[0].value == "Tony Stark"
        assert all_versions[0].is_active is False
        
        # Version 2 is active
        assert all_versions[1].value == "Iron Man"
        assert all_versions[1].is_active is True

    # 2. Multi-value relational storage (no overwriting, normalized rows)
    print("Saving liked language: 'I like Python.'")
    await memory_service._async_extract_and_save("I like Python.")
    print("Saving liked language: 'I like Java.'")
    await memory_service._async_extract_and_save("I like Java.")
    
    # Verify they exist as separate rows in preferences
    prefs = await memory_service.sqlite_repo.search_preferences("like")
    prefs_vals = [p["value"] for p in prefs]
    assert "likes Python" in prefs_vals or "likes python" in prefs_vals
    assert "likes Java" in prefs_vals or "likes java" in prefs_vals
    
    # Verify duplicates are prevented (access counts updated instead of new insertion)
    initial_count = len(prefs)
    await memory_service._async_extract_and_save("I like Java.")
    reloaded_prefs = await memory_service.sqlite_repo.search_preferences("like")
    assert len(reloaded_prefs) == initial_count  # No duplicate row created
    
    print("Conflict Resolution & Versioning tests PASSED.")

async def test_decay_and_aging():
    print("\n--- Testing Aging, Archive, & Reactivation ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    
    # Save a low-importance memory fact
    print("Saving fact: 'I work as a software tester.'")
    await memory_service._async_extract_and_save("I work as a software tester.")
    
    facts = await memory_service.sqlite_repo.search_facts("occupation")
    assert len(facts) == 1
    record_id = facts[0]["id"]
    
    # Force last_accessed_at to 10 days ago (threshold for low is 7 days)
    async with get_async_session() as session:
        stmt = select(UserFactModel).where(UserFactModel.id == record_id)
        res = await session.execute(stmt)
        record = res.scalars().first()
        record.last_accessed_at = datetime.utcnow() - timedelta(days=10)
        record.importance = 20  # Low importance
        await session.flush()
        
    # Trigger decay lifecycle
    await memory_service.decay_service.decay_memories()
    
    # Retrieve: standard lookup should return empty (since it's archived)
    standard_context = await memory_service.retrieve_context("What is my occupation?")
    assert "software tester" not in standard_context
    
    # Retrieve with archive override query keyword
    archive_context = await memory_service.retrieve_context("What is my occupation? Check archive.")
    assert "software tester" in archive_context
    
    # Verify reversible unarchiving (the memory should now be unarchived and active again!)
    facts_after = await memory_service.sqlite_repo.search_facts("occupation")
    assert len(facts_after) == 1
    assert facts_after[0]["is_archived"] is False
    
    print("Decay and Aging tests PASSED.")

async def test_concurrency_control():
    print("\n--- Testing Concurrency Controls ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    
    # Save fact
    await memory_service.sqlite_repo.save_fact("identity", "favorite_color", "blue", 1.0, 50)
    
    fact = await memory_service.sqlite_repo.get_active_fact("identity", "favorite_color")
    assert fact is not None
    assert fact["version"] == 1
    
    # Simulate concurrency update conflict
    # Deactivate color but pass incorrect expected_version (e.g. 5)
    success = await memory_service.sqlite_repo.deactivate_record("user_facts", fact["id"], expected_version=5)
    assert success is False  # Fails due to stale version check
    
    # Deactivate with correct expected_version (1)
    success_real = await memory_service.sqlite_repo.deactivate_record("user_facts", fact["id"], expected_version=1)
    assert success_real is True
    
    print("Concurrency Control tests PASSED.")

async def test_soft_deletions():
    print("\n--- Testing Soft Deletions ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    await memory_service._async_extract_and_save("My name is Tony Stark.")
    
    # Verify exists
    facts_before = await memory_service.sqlite_repo.search_facts("name")
    assert len(facts_before) == 1
    
    # Soft delete the fact
    deleted = await memory_service.sqlite_repo.delete_fact(key="name")
    assert deleted is True
    
    # Verify excluded from normal search query retrieval
    facts_after = await memory_service.sqlite_repo.search_facts("name")
    assert len(facts_after) == 0
    
    print("Soft Deletion tests PASSED.")

async def test_transaction_consistency_and_retry():
    print("\n--- Testing Transaction Consistency & Background Retry ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    
    # Mock ChromaDB fail
    original_save = memory_service.chroma_repo.save_embedding
    
    def mock_save_embedding_fail(*args, **kwargs):
        raise RuntimeError("Mock ChromaDB connection loss!")
        
    memory_service.chroma_repo.save_embedding = mock_save_embedding_fail
    
    # Trigger extract and save - SQLite should succeed, ChromaDB fails and gets flagged
    print("Extracting fact with mock vector database failure...")
    await memory_service._async_extract_and_save("My name is Tony Stark.")
    
    # Verify relational data is saved
    facts = await memory_service.sqlite_repo.search_facts("name")
    assert len(facts) == 1
    record_id = facts[0]["id"]
    
    # Verify metadata is marked as pending_index = True
    async with get_async_session() as session:
        stmt = select(MemoryMetadataModel).where(MemoryMetadataModel.record_id == record_id)
        res = await session.execute(stmt)
        meta = res.scalars().first()
        assert meta is not None
        assert meta.pending_index is True
        assert meta.status == "pending"
        
    # Restore ChromaDB connection
    memory_service.chroma_repo.save_embedding = original_save
    
    # Trigger background retry daemon loop
    print("Restoring vector database and running background index retry...")
    await memory_service.decay_service.retry_pending_indexes()
    
    # Verify pending index cleared
    async with get_async_session() as session:
        stmt2 = select(MemoryMetadataModel).where(MemoryMetadataModel.record_id == record_id)
        res2 = await session.execute(stmt2)
        meta2 = res2.scalars().first()
        assert meta2.pending_index is False
        assert meta2.status == "active"
        
    print("Transaction Consistency & Index Retry tests PASSED.")

async def test_advanced_memory_versioning():
    print("\n--- Testing Advanced Memory Versioning Logic ---")
    await clear_database()
    
    memory_service = MemoryFactory.get_memory_service()
    
    # Scenario A: Tony -> Iron Man -> "What is my name?" => Iron Man
    print("A1. Saving name: 'My name is Tony.'")
    await memory_service._async_extract_and_save("My name is Tony.")
    
    print("A2. Saving update: 'Actually my name is Iron Man.'")
    await memory_service._async_extract_and_save("Actually my name is Iron Man.")
    
    print("A3. Retrieving context for 'What is my name?'")
    context_name = await memory_service.retrieve_long_term_context("What is my name?")
    print(f"Context name: '{context_name}'")
    assert "Iron Man" in context_name
    assert "Tony" not in context_name  # Inactive version MUST be ignored
    
    # Scenario B: Java -> Python favourite language => Python
    print("B1. Saving preference: 'My favourite language is Java.'")
    await memory_service._async_extract_and_save("My favourite language is Java.")
    
    print("B2. Saving preference update: 'My favorite language is Python.'")
    await memory_service._async_extract_and_save("My favorite language is Python.")
    
    print("B3. Retrieving context for 'What is my favourite language?'")
    context_lang = await memory_service.retrieve_long_term_context("What is my favourite language?")
    print(f"Context lang: '{context_lang}'")
    assert "Python" in context_lang
    assert "Java" not in context_lang  # Inactive version MUST be ignored
    
    # Scenario C: "What was my previous name?" => Tony
    print("C1. Retrieving context for 'What was my previous name?'")
    context_prev_name = await memory_service.retrieve_long_term_context("What was my previous name?")
    print(f"Context previous name: '{context_prev_name}'")
    assert "Tony" in context_prev_name  # Inactive versions should be loaded when query explicitly asks for previous/history/version
    assert "Iron Man" in context_prev_name
    
    # Scenario D: Verify inactive memories are never injected into normal prompts
    print("D1. Retrieving normal context without history/previous keywords")
    normal_context_name = await memory_service.retrieve_long_term_context("Tell me my name.")
    print(f"Normal context name: '{normal_context_name}'")
    assert "Tony" not in normal_context_name
    assert "Iron Man" in normal_context_name
    
    normal_context_lang = await memory_service.retrieve_long_term_context("Tell me my favorite language.")
    print(f"Normal context lang: '{normal_context_lang}'")
    assert "Java" not in normal_context_lang
    assert "Python" in normal_context_lang
    
    print("Advanced Memory Versioning tests PASSED.")

async def main():
    print("============================================================")
    print("      JARVIS ADVANCED MEMORY (PHASE 4.1) TEST SUITE")
    print("============================================================")
    await init_db()
    
    # Start memory background service loop safely
    memory_service = MemoryFactory.get_memory_service()
    memory_service.start()
    
    try:
        await test_memory_filter()
        await test_hybrid_extraction()
        await test_conflict_resolution_and_versioning()
        await test_advanced_memory_versioning()
        await test_decay_and_aging()
        await test_concurrency_control()
        await test_soft_deletions()
        await test_transaction_consistency_and_retry()
        print("\nAll Phase 4.1 advanced memory checks PASSED successfully!")
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Gracefully shut down background loop tasks to prevent runtime warnings or hung scripts
        try:
            await memory_service.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
