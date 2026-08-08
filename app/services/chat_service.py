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
        
        # 1. Intent Classification
        classification_start = time.perf_counter()
        intent = IntentClassifier.classify(request.message)
        classification_latency = time.perf_counter() - classification_start
        
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

        # 3. Cache Invalidation (if this request updates memory facts/preferences)
        if intent == "memory_update":
            self._response_cache.invalidate_session(session_id)

        # 4. Memory Context Retrieval
        retrieval_start = time.perf_counter()
        long_term_context = ""
        semantic_context = ""
        profile_context = ""
        graph_context = ""
        
        try:
            long_term_context = await self.memory_service.retrieve_long_term_context(request.message)
            semantic_context = await self.memory_service.retrieve_semantic_context(request.message)
            
            # Fetch User Profile Context
            if settings.ENABLE_USER_PROFILE and hasattr(self.memory_service, "user_profile_engine") and self.memory_service.user_profile_engine:
                prof_data = await self.memory_service.user_profile_engine.get_profile_context(session_id)
                if prof_data:
                    profile_context = "\n".join(f"- {k}: {v}" for k, v in prof_data.items())
                    
            # Fetch Knowledge Graph Context
            if settings.ENABLE_GRAPH and hasattr(self.memory_service, "graph_service") and self.memory_service.graph_service:
                seed_entities = []
                # Pronoun referent resolution
                if settings.ENABLE_ALIAS_RESOLUTION and hasattr(self.memory_service, "pronoun_resolver") and self.memory_service.pronoun_resolver:
                    try:
                        recent_convs = await self.memory_service.sqlite_repo.list_conversations(session_id, limit=5)
                        recent_msg_list = [{"role": c["role"], "content": c["content"]} for c in recent_convs]
                        ref_ent = await self.memory_service.pronoun_resolver.resolve_referent(request.message, recent_msg_list)
                        if ref_ent:
                            seed_entities.append(ref_ent["canonical_name"])
                    except Exception as ex_pronoun:
                        logger.warning(f"Failed pronoun resolution check: {ex_pronoun}")
                
                # Scan query for entity names
                try:
                    all_entities = await self.memory_service.entity_repo.list_entities(limit=200)
                    for ent in all_entities:
                        if ent["canonical_name"].lower() in request.message.lower() and ent["canonical_name"] not in seed_entities:
                            seed_entities.append(ent["canonical_name"])
                except Exception as ex_ent:
                    logger.warning(f"Failed entity name matching: {ex_ent}")
                    
                if seed_entities:
                    facts = await self.memory_service.graph_service.expand_context(seed_entities, max_depth=2)
                    if facts:
                        graph_context = "\n".join(facts)
        except Exception as graph_err:
            logger.error(f"Error retrieving advanced cognitive contexts, falling back: {graph_err}", exc_info=True)
            # Fallback to standard context retrieval
            try:
                long_term_context = await self.memory_service.retrieve_long_term_context(request.message)
                semantic_context = await self.memory_service.retrieve_semantic_context(request.message)
            except Exception:
                pass

        # Dynamic Token Budgeting (Priority order: Profile > Direct > Semantic > Graph > Timeline)
        max_chars = 16000
        current_chars = 0
        
        # 1. User Profile
        if profile_context:
            if current_chars + len(profile_context) <= max_chars:
                current_chars += len(profile_context)
            else:
                profile_context = ""
                
        # 2. Direct Memory
        if long_term_context:
            if current_chars + len(long_term_context) <= max_chars:
                current_chars += len(long_term_context)
            else:
                long_term_context = ""
                
        # 3. Semantic Memory
        if semantic_context:
            if current_chars + len(semantic_context) <= max_chars:
                current_chars += len(semantic_context)
            else:
                semantic_context = ""
                
        # 4. Graph Context
        if graph_context:
            if current_chars + len(graph_context) <= max_chars:
                current_chars += len(graph_context)
            else:
                graph_context = ""

        retrieval_latency = time.perf_counter() - retrieval_start
 
        # 5. Prompt Construction and Timeline Context Retrieval
        prompt_start = time.perf_counter()
        
        timeline_context = ""
        if intent in ("schedule_query", "timeline_query", "event_query"):
            from app.services.cognitive.timeline_engine import TimelineEngine
            from datetime import timedelta
            timeline_engine = TimelineEngine(self.memory_service.event_repository)
            
            view = "upcoming"
            ref_time = datetime.utcnow()
            q_lower = request.message.lower()
            
            if "today" in q_lower:
                view = "daily"
                ref_time = datetime.utcnow()
            elif "tomorrow" in q_lower:
                view = "daily"
                ref_time = datetime.utcnow() + timedelta(days=1)
            elif "yesterday" in q_lower:
                view = "daily"
                ref_time = datetime.utcnow() - timedelta(days=1)
            elif "week" in q_lower:
                view = "weekly"
            elif "month" in q_lower:
                view = "monthly"
            elif "upcoming" in q_lower or "coming" in q_lower or "next" in q_lower or "future" in q_lower:
                view = "upcoming"
            elif "overdue" in q_lower or "missed" in q_lower or "late" in q_lower:
                view = "overdue"
            elif "completed" in q_lower or "done" in q_lower or "finished" in q_lower:
                view = "completed"
            elif "cancelled" in q_lower or "canceled" in q_lower:
                view = "cancelled"
            elif "milestone" in q_lower or "deadline" in q_lower or "project" in q_lower:
                view = "project"
            elif "timeline" in q_lower or "history" in q_lower:
                view = "all"
                
            events = await timeline_engine.generate_timeline(session_id, view=view, start_date=ref_time)
            if events:
                lines = []
                for ev in events:
                    start_str = ev["start_time"].isoformat()
                    end_str = ev["end_time"].isoformat() if ev.get("end_time") else "None"
                    lines.append(
                        f"- [{ev['event_type'].upper()}] {ev['title']}: "
                        f"Start: {start_str}, End: {end_str}, "
                        f"Status: {ev['status']}, Importance: {ev['importance']}, "
                        f"Confidence: {ev.get('confidence', 1.0)}"
                    )
                timeline_context = "\n".join(lines)
            else:
                timeline_context = "No events scheduled or found for this period."

        # Budget Timeline Context
        if timeline_context:
            if current_chars + len(timeline_context) <= max_chars:
                current_chars += len(timeline_context)
            else:
                timeline_context = "No events scheduled or found for this period."

        system_prompt = self.prompt_builder.build_system_prompt(
            intent=intent,
            long_term_context=long_term_context,
            semantic_context=semantic_context,
            timeline_context=timeline_context,
            is_voice=request.is_voice,
            profile_context=profile_context,
            graph_context=graph_context
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
        
        # Save exchange and extract facts in background (non-blocking)
        asyncio.create_task(self.memory_service.save_exchange(session_id, request.message, validated_response))
        asyncio.create_task(self.memory_service.extract_and_save_memories(request.message, session_id))

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
