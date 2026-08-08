"""
Chat Service implementation.
"""
import time
import logging
import asyncio
from typing import List, Dict, Optional

from app.services.interfaces.base_chat_service import BaseChatService
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.services.response.intent_classifier import IntentClassifier
from app.services.response.response_cache import ResponseCache
from app.services.response.prompt_builder import PromptBuilder
from app.services.response.post_processor import ResponsePostProcessor
from app.services.response.response_validator import ResponseValidator
from app.config.settings import settings
from memory.base import BaseMemory
from app.models.chat_models import ChatRequest
from app.core.dependencies import get_llm, get_memory

logger = logging.getLogger("jarvis")

class ChatService(BaseChatService):
    """
    ChatService implements BaseChatService to orchestrate prompt resolution,
    history memory extraction, LLM service invocation, and analytics.
    """
    # Shared response cache singleton to persist hits across FastAPI request instantiations
    _response_cache = ResponseCache(ttl_seconds=settings.RESPONSE_CACHE_TTL)

    def __init__(self, llm: BaseLLM = None, memory: BaseMemory = None, memory_service = None):
        self.llm = llm or get_llm()
        self.memory = memory or get_memory()
        self.prompt_builder = PromptBuilder()
        
        if memory_service:
            self.memory_service = memory_service
        else:
            from app.services.factory import ServiceFactory
            self.memory_service = ServiceFactory.get_memory_service()

    async def execute_chat(self, request: ChatRequest) -> str:
        session_id = request.session_id
        
        # Intercept desktop and browser action pending confirmations
        from app.services.factory import ServiceFactory
        desktop_service = ServiceFactory.get_desktop_automation_service()
        browser_service = ServiceFactory.get_browser_automation_service()
        agent_service = ServiceFactory.get_agent_service()
        
        if session_id in desktop_service._pending_confirmations:
            pending = desktop_service._pending_confirmations[session_id]
            if "agent_plan_id" in pending:
                result = await agent_service.execute_goal(request.message, session_id)
            else:
                result = await desktop_service.execute_action(session_id, request.message)
            await self.memory.add_message(session_id, "user", request.message)
            await self.memory.add_message(session_id, "assistant", result)
            return result

        elif session_id in browser_service._pending_confirmations:
            pending = browser_service._pending_confirmations[session_id]
            if "agent_plan_id" in pending:
                result = await agent_service.execute_goal(request.message, session_id)
            else:
                result = await browser_service.execute_action(session_id, request.message)
            await self.memory.add_message(session_id, "user", request.message)
            await self.memory.add_message(session_id, "assistant", result)
            return result
        
        # 1. Intent Classification
        classification_start = time.perf_counter()
        intent = IntentClassifier.classify(request.message)
        classification_latency = time.perf_counter() - classification_start
        
        # Intercept new complex goal agent runs
        if intent == "complex_goal":
            result = await agent_service.execute_goal(request.message, session_id)
            await self.memory.add_message(session_id, "user", request.message)
            await self.memory.add_message(session_id, "assistant", result)
            return result
            
        # Intercept new desktop actions
        if intent == "desktop_action":
            result = await desktop_service.execute_action(session_id, request.message)
            await self.memory.add_message(session_id, "user", request.message)
            await self.memory.add_message(session_id, "assistant", result)
            return result

        # Intercept new browser actions
        if intent == "browser_action":
            result = await browser_service.execute_action(session_id, request.message)
            await self.memory.add_message(session_id, "user", request.message)
            await self.memory.add_message(session_id, "assistant", result)
            return result

        
        # 2. Cache Lookup (only for memory recall and simple facts)
        if intent in ("memory_recall", "simple_fact_question"):
            cached_val = self._response_cache.get(session_id, request.message)
            if cached_val:
                word_count = len(cached_val.split())
                logger.info(
                    f"Chat Service Execution [Cache Hit] | Session: {session_id} | "
                    f"Intent: {intent} | Word Count: {word_count} | "
                    f"Classification Latency: {classification_latency:.4f}s | "
                    f"Prompt Version: {settings.PROMPT_VERSION} | Voice Mode: {request.is_voice}"
                )
                return cached_val

        # 3. Cache Invalidation (if this request updates memory facts/preferences/tasks)
        if intent in ("memory_update", "task_create", "task_update", "habit_update"):
            self._response_cache.invalidate_session(session_id)

        # 4. Memory Context Retrieval & Cognitive Reasoning
        retrieval_start = time.perf_counter()
        try:
            cognitive_reasoner = ServiceFactory.get_cognitive_reasoner()
            budgeted_contexts = await cognitive_reasoner.reason_over_context(
                request.message, session_id, intent
            )
            profile_context = budgeted_contexts.get("profile_context", "")
            long_term_context = budgeted_contexts.get("long_term_context", "")
            semantic_context = budgeted_contexts.get("semantic_context", "")
            graph_context = budgeted_contexts.get("graph_context", "")
            timeline_context = budgeted_contexts.get("timeline_context", "")
            task_context = budgeted_contexts.get("task_context", "")
        except Exception as reasoner_err:
            logger.error(f"CognitiveReasoner failed, falling back: {reasoner_err}", exc_info=True)
            profile_context = ""
            long_term_context = ""
            semantic_context = ""
            graph_context = ""
            timeline_context = ""
            task_context = ""

        retrieval_latency = time.perf_counter() - retrieval_start
 
        # 5. Prompt Construction
        prompt_start = time.perf_counter()
        system_prompt = self.prompt_builder.build_system_prompt(
            intent=intent,
            long_term_context=long_term_context,
            semantic_context=semantic_context,
            timeline_context=timeline_context,
            is_voice=request.is_voice,
            profile_context=profile_context,
            graph_context=graph_context,
            task_context=task_context
        )
        prompt_latency = time.perf_counter() - prompt_start

        # 6. Retrieve short-term history
        history = await self.memory.get_history(session_id)

        # 7. Configure Generation (determinism temperature=0.0 for memory recall)
        gen_config = None
        if intent == "memory_recall":
            gen_config = GenerationConfig(temperature=0.0)

        # 8. Call LLM provider
        llm_start = time.perf_counter()
        llm_result = await self.llm.generate_response(
            request,
            system_prompt,
            history=history,
            config=gen_config
        )
        llm_latency = time.perf_counter() - llm_start

        # 9. Clean response with ResponsePostProcessor
        post_start = time.perf_counter()
        cleaned_response = ResponsePostProcessor.process(llm_result.response, intent=intent)
        post_latency = time.perf_counter() - post_start

        # 10. Fetch correct context values to validate memory recalls
        context_values = []
        if intent == "memory_recall":
            raw_memories = await self.memory_service.search_service.search_relational_memories(request.message)
            context_values = [m.get("value") for m in raw_memories if m.get("value")]

        # Determine appropriate word limit for this mode
        if request.is_voice and intent == "memory_recall":
            max_words = 15
        elif intent == "memory_recall":
            max_words = settings.MAX_MEMORY_RESPONSE_WORDS
        elif intent == "simple_fact_question":
            max_words = settings.MAX_FACT_RESPONSE_WORDS
        elif intent == "explanation":
            max_words = settings.MAX_EXPLANATION_RESPONSE_WORDS
        else:
            max_words = settings.MAX_GENERAL_RESPONSE_WORDS

        # 11. Run ResponseValidator
        validated_response = ResponseValidator.validate(
            response=cleaned_response,
            context_values=context_values,
            max_words=max_words,
            intent=intent
        )

        # 12. Save to Cache on success
        if intent in ("memory_recall", "simple_fact_question") and validated_response:
            self._response_cache.set(session_id, request.message, validated_response)

        # 13. Save interaction history
        await self.memory.add_message(session_id, "user", request.message)
        await self.memory.add_message(session_id, "assistant", validated_response)
        
        # Save exchange, extract facts, and compress history in background (non-blocking)
        asyncio.create_task(self.memory_service.save_exchange(session_id, request.message, validated_response))
        asyncio.create_task(self.memory_service.extract_and_save_memories(request.message, session_id))
        try:
            summary_service = ServiceFactory.get_memory_summary_service()
            asyncio.create_task(summary_service.compress_session_history(session_id))
        except Exception as comp_err:
            logger.warning(f"Failed to spawn conversation compression task: {comp_err}")

        # 14. Emit telemetry logging
        word_count = len(validated_response.split())
        usage_log = ""
        if llm_result.total_tokens is not None:
            usage_log = (
                f" | Tokens: prompt={llm_result.input_tokens}, "
                f"completion={llm_result.output_tokens}, total={llm_result.total_tokens}"
                f" | Latency: classification={classification_latency:.4f}s, "
                f"retrieval={retrieval_latency:.4f}s, prompt={prompt_latency:.4f}s, "
                f"llm={llm_latency:.4f}s, post_processing={post_latency:.4f}s"
            )
        logger.info(
            f"Chat Service Execution [Cache Miss] | Session: {session_id} | "
            f"Intent: {intent} | Word Count: {word_count} | "
            f"Provider: {llm_result.provider} | Model: {llm_result.model}{usage_log} | "
            f"Prompt Version: {settings.PROMPT_VERSION} | Voice Mode: {request.is_voice}"
        )

        return validated_response
