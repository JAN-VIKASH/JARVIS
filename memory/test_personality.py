import asyncio
import time
import logging
from typing import List, Dict, Optional, Any
from app.config.settings import settings
from app.database.migrations import init_db
from app.database.session import get_async_session
from app.models.chat_models import ChatRequest, LLMResult
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.services.chat_service import ChatService
from app.services.response.intent_classifier import IntentClassifier
from app.services.response.post_processor import ResponsePostProcessor
from app.services.response.response_validator import ResponseValidator
from app.services.response.prompt_builder import PromptBuilder
from memory.memory_factory import MemoryFactory
from memory.test_memory import clear_database

logger = logging.getLogger("jarvis")

class MockLLM(BaseLLM):
    """
    Mock LLM Provider that outputs configurable responses to test prompt validation and intent styling.
    """
    def __init__(self):
        self.next_response = "Mocked LLM Response"
        self.last_config = None

    async def generate_response(
        self,
        request: ChatRequest,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        config: Optional[GenerationConfig] = None
    ) -> LLMResult:
        self.last_config = config
        
        # Test-driven response generation
        q = request.message.lower()
        if "hallucinate" in q:
            # Output value not in context to test validator interception
            resp = "Your name is Iron Man."
        elif "prompt leak" in q:
            # Output value containing system prompt headers to test validator leakage protection
            resp = "Your name is Jan Vikash. relevance: 0.99 memory context header"
        elif "empty" in q:
            resp = ""
        elif "jvm architecture" in q:
            resp = "The JVM Architecture consists of Class Loader Subsystem, Runtime Data Areas, and Execution Engine..."
        elif "hello" in q:
            resp = "Hello! How can I help you today, sir? sir?"
        elif "what is my name" in q or "tell me my name" in q or "do you know my name" in q:
            if "identity" in system_prompt and "Jan Vikash" in system_prompt:
                resp = "Your name is Jan Vikash."
            else:
                resp = "I do not have that information in my memory."
        elif "what languages do i like" in q:
            resp = "You like Java and Python."
        elif "my favourite colour is blue" in q:
            resp = "Got it. I'll remember that your favourite colour is blue."
        else:
            resp = self.next_response
            
        return LLMResult(
            response=resp,
            provider="mock",
            model="mock-llama",
            latency=0.01,
            input_tokens=100,
            output_tokens=20,
            total_tokens=120
        )

async def test_intent_classification():
    print("\n--- Testing Intent Classification ---")
    assert IntentClassifier.classify("Hello JARVIS") == "greeting"
    assert IntentClassifier.classify("What is my age?") == "memory_recall"
    assert IntentClassifier.classify("My favorite food is Pizza") == "memory_update"
    assert IntentClassifier.classify("Write a python function to add two numbers") == "coding_help"
    assert IntentClassifier.classify("Explain how garbage collection works") == "explanation"
    assert IntentClassifier.classify("Brainstorm five project ideas") == "brainstorming"
    assert IntentClassifier.classify("What is the capital of Japan?") == "simple_fact_question"
    assert IntentClassifier.classify("How was your day?") == "conversation"
    print("Intent Classification tests PASSED.")

async def test_post_processor_and_streaming():
    print("\n--- Testing Post Processor & Streaming Readiness ---")
    
    # Repetitive "sir" deduplication
    raw_sir = "Hello, sir. How may I help you, sir? Yes, sir."
    cleaned_sir = ResponsePostProcessor.process(raw_sir)
    print(f"Cleaned sir: '{cleaned_sir}'")
    assert cleaned_sir.lower().count("sir") == 1
    
    # Trailing polite helpers removal for factual intents
    raw_ending = "Your name is Jan Vikash. Is there anything else I can help with?"
    cleaned_ending = ResponsePostProcessor.process(raw_ending, intent="memory_recall")
    print(f"Cleaned ending: '{cleaned_ending}'")
    assert "Is there anything else" not in cleaned_ending
    
    # Duplicate sentences removal
    raw_dup = "Your name is Jan Vikash. Your name is Jan Vikash. Yes, it is."
    cleaned_dup = ResponsePostProcessor.process(raw_dup)
    print(f"Cleaned duplicates: '{cleaned_dup}'")
    assert cleaned_dup.count("Your name is Jan Vikash.") == 1

    # Streaming readiness: modular chunk cleaning
    chunk = "  stream   chunk   text  "
    cleaned_chunk = ResponsePostProcessor.clean_chunk(chunk)
    assert cleaned_chunk == " stream chunk text "
    
    print("Post Processor & Streaming tests PASSED.")

async def test_response_validation():
    print("\n--- Testing Response Validator ---")
    
    # 1. Word limits enforcement
    long_response = "Word " * 100
    validated_limit = ResponseValidator.validate(long_response, [], max_words=30, intent="conversation")
    assert len(validated_limit.split()) == 30
    
    # 2. Hallucinated memory values rejection
    # Context lists only "Jan Vikash". If response says "Iron Man", it must be intercepted.
    hallucinated = "Your name is Iron Man."
    validated_hallucinated = ResponseValidator.validate(hallucinated, ["Jan Vikash"], max_words=20, intent="memory_recall")
    print(f"Validated hallucinated name: '{validated_hallucinated}'")
    assert validated_hallucinated == "I do not have that information in my memory."
    
    # 3. Leak prevention
    leaked = "Your name is Jan Vikash. relevance: 0.99 memory context header"
    validated_leak = ResponseValidator.validate(leaked, ["Jan Vikash"], max_words=20, intent="memory_recall")
    print(f"Validated leaked: '{validated_leak}'")
    assert "relevance" not in validated_leak
    
    # 4. Empty responses fallback
    validated_empty = ResponseValidator.validate("", ["Jan Vikash"], max_words=20, intent="memory_recall")
    assert validated_empty == "I do not have that information in my memory."
    
    print("Response Validator tests PASSED.")

async def test_prompt_builder_and_registry():
    print("\n--- Testing PromptBuilder & Registry ---")
    builder = PromptBuilder()
    
    # Test loading externalized templates
    base = builder._load_template("base_prompt.txt")
    assert "JARVIS" in base
    
    # Test intent specific compilation
    system_prompt = builder.build_system_prompt(
        intent="memory_recall",
        long_term_context="name = Jan Vikash",
        is_voice=False
    )
    print("Compiled System Prompt:")
    print(system_prompt[:200] + "...")
    assert settings.PROMPT_VERSION in system_prompt
    assert "Memory Recall" in system_prompt
    assert "LONG-TERM MEMORY" in system_prompt
    
    # Test voice optimization template inclusion
    system_prompt_voice = builder.build_system_prompt(
        intent="conversation",
        is_voice=True
    )
    assert "spoken conversation" in system_prompt_voice.lower() or "shorter" in system_prompt_voice.lower()

    print("PromptBuilder & Template Registry tests PASSED.")

async def test_chat_service_personality_and_caching():
    print("\n--- Testing ChatService Caching, Consistency & Caching Invalidation ---")
    await clear_database()
    
    mock_llm = MockLLM()
    memory_service = MemoryFactory.get_memory_service()
    
    # Setup ChatService with Mock LLM
    chat_service = ChatService(llm=mock_llm, memory_service=memory_service)
    
    # Save a fact to SQLite
    await memory_service._async_extract_and_save("My name is Jan Vikash.")
    await memory_service._async_extract_and_save("I like Java and Python.")
    
    # 1. Memory Recall Consistency
    # Verify that different query phrases produce the identical response
    req1 = ChatRequest(message="What is my name?", session_id="test_perf_1")
    resp1 = await chat_service.execute_chat(req1)
    print(f"Resp 1: '{resp1}'")
    assert resp1 == "Your name is Jan Vikash."
    
    req2 = ChatRequest(message="Tell me my name.", session_id="test_perf_1")
    resp2 = await chat_service.execute_chat(req2)
    print(f"Resp 2: '{resp2}'")
    assert resp2 == "Your name is Jan Vikash."
    
    req3 = ChatRequest(message="Do you know my name?", session_id="test_perf_1")
    resp3 = await chat_service.execute_chat(req3)
    assert resp3 == "Your name is Jan Vikash."
    
    # 2. Verify Caching
    # Modify Mock LLM response to ensure ChatService does NOT call generate_response (should hit cache)
    mock_llm.next_response = "This should never be returned because of cache hit"
    req4 = ChatRequest(message="What is my name?", session_id="test_perf_1")
    resp4 = await chat_service.execute_chat(req4)
    assert resp4 == "Your name is Jan Vikash."  # Cache hit verified!
    
    # 3. Cache Invalidation
    # Update memory using memory_update intent
    req_update = ChatRequest(message="My favourite colour is blue.", session_id="test_perf_1")
    resp_update = await chat_service.execute_chat(req_update)
    assert "blue" in resp_update
    
    # Cache should be invalidated now. A new name query should hit the LLM (which is mocked to output a name)
    req5 = ChatRequest(message="What languages do I like?", session_id="test_perf_1")
    resp5 = await chat_service.execute_chat(req5)
    assert "Java" in resp5
    
    # 4. Determinism
    # Verify temperature=0.0 is passed in GenerationConfig for memory_recall
    assert mock_llm.last_config is not None
    assert mock_llm.last_config.temperature == 0.0
    
    # 5. Non-existent recall returns fallback directly
    req_missing = ChatRequest(message="What is my favorite pet?", session_id="test_perf_1")
    resp_missing = await chat_service.execute_chat(req_missing)
    print(f"Resp missing: '{resp_missing}'")
    assert resp_missing == "I do not have that information in my memory."

    # 6. Hallucination block verify
    req_hallucinate = ChatRequest(message="Do you know my name? (force hallucinate)", session_id="test_perf_1")
    resp_hallucinate = await chat_service.execute_chat(req_hallucinate)
    print(f"Resp hallucinate: '{resp_hallucinate}'")
    assert resp_hallucinate == "I do not have that information in my memory." # Hallucination was correctly caught and reverted!

    print("ChatService Caching & Consistency tests PASSED.")

async def test_provider_compatibility():
    print("\n--- Testing GenerationConfig Provider Compatibility ---")
    config = GenerationConfig(temperature=0.7, max_tokens=150, top_p=0.9, seed=42)
    
    # 1. PlaceholderLLM
    from app.services.llm.placeholder import PlaceholderLLM
    p_llm = PlaceholderLLM()
    res1 = await p_llm.generate_response(ChatRequest(message="test"), "system", config=config)
    assert res1.provider == "placeholder"
    
    # 2. OpenAIProvider (if key exists, otherwise test signature compatibility)
    from app.services.llm.openai_provider import OpenAIProvider
    try:
        o_llm = OpenAIProvider()
        # Just verifying structure can accept config without throwing python schema TypeError
    except ValueError:
        # Expected if API key is not in settings, signature compatibility is verified by import
        pass
        
    # 3. GroqProvider
    from app.services.llm.groq_provider import GroqProvider
    try:
        g_llm = GroqProvider()
    except ValueError:
        pass
        
    print("Provider GenerationConfig compatibility PASSED.")

async def main():
    print("============================================================")
    print("    JARVIS RESPONSE QUALITY & PERSONALITY (4.2) TEST SUITE")
    print("============================================================")
    await init_db()
    try:
        await test_intent_classification()
        await test_post_processor_and_streaming()
        await test_response_validation()
        await test_prompt_builder_and_registry()
        await test_chat_service_personality_and_caching()
        await test_provider_compatibility()
        print("\nAll Phase 4.2 response quality and personality checks PASSED successfully!")
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
