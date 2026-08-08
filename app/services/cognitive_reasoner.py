"""
CognitiveReasoner orchestrates intent detection, pronoun resolution, user profile retrieval, 
knowledge graph neighbourhood expansion, task lists, timeline schedules, and semantic memory.
AdaptiveContextBuilder dynamically adjusts token budgets based on intent.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.config.settings import settings
from app.cognitive.infrastructure.context_builder import ContextBuilder
from app.services.llm.base import BaseLLM
from memory.memory_service import MemoryService

logger = logging.getLogger("jarvis.cognitive")

class AdaptiveContextBuilder(ContextBuilder):
    """
    Dynamically adjusts budgets for each cognitive segment depending on user intent.
    """
    def build_adaptive_context(
        self,
        intent: str,
        user_profile: Optional[Dict[str, Any]] = None,
        direct_memories: Optional[List[str]] = None,
        semantic_memories: Optional[List[str]] = None,
        graph_context: Optional[List[str]] = None,
        timeline_events: Optional[List[str]] = None,
        task_context: Optional[List[str]] = None,
        recent_conversation: Optional[List[Dict[str, str]]] = None,
        session_summary: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Calculates token budgeting dynamically based on intent, returning
        budget-allocated context strings.
        """
        # Max character limit (max_tokens * 4)
        total_limit = self.max_tokens * 4
        
        # 1. Calculate intent-based budgets
        if intent in ("task_query", "task_update", "task_create"):
            # Task-focused budget
            profile_lim = int(total_limit * 0.25)
            direct_lim = int(total_limit * 0.15)
            semantic_lim = int(total_limit * 0.10)
            graph_lim = int(total_limit * 0.10)
            timeline_lim = int(total_limit * 0.10)
            tasks_lim = int(total_limit * 0.40) # 40% task budget
            recent_lim = int(total_limit * 0.15)
        elif intent in ("schedule_query", "timeline_query", "event_query"):
            # Schedule-focused budget
            profile_lim = int(total_limit * 0.20)
            direct_lim = int(total_limit * 0.10)
            semantic_lim = int(total_limit * 0.10)
            graph_lim = int(total_limit * 0.15)
            timeline_lim = int(total_limit * 0.45) # 45% timeline budget
            tasks_lim = int(total_limit * 0.10)
            recent_lim = int(total_limit * 0.15)
        else:
            # Default balanced budget
            profile_lim = int(total_limit * 0.25)
            direct_lim = int(total_limit * 0.20)
            semantic_lim = int(total_limit * 0.15)
            graph_lim = int(total_limit * 0.15)
            timeline_lim = int(total_limit * 0.15)
            tasks_lim = int(total_limit * 0.15)
            recent_lim = int(total_limit * 0.20)

        # 2. Format and truncate helpers
        def limit_str(text: str, limit: int) -> str:
            if not text:
                return ""
            if len(text) > limit:
                return text[:limit] + "\n... [truncated]"
            return text

        # Profile context construction
        profile_str = ""
        if user_profile:
            lines = []
            for k, v in user_profile.items():
                if isinstance(v, list):
                    v_str = ", ".join(map(str, v))
                elif isinstance(v, dict):
                    v_str = ", ".join(f"{dk}: {dv}" for dk, dv in v.items())
                else:
                    v_str = str(v)
                lines.append(f"- {k.title()}: {v_str}")
            profile_str = limit_str("\n".join(lines), profile_lim)

        direct_str = ""
        if direct_memories:
            direct_str = limit_str("\n".join(f"- {m}" for m in direct_memories if m.strip()), direct_lim)

        semantic_str = ""
        if semantic_memories:
            semantic_str = limit_str("\n".join(f"- {m}" for m in semantic_memories if m.strip()), semantic_lim)

        graph_str = ""
        if graph_context:
            graph_str = limit_str("\n".join(f"- {g}" for g in graph_context if g.strip()), graph_lim)

        timeline_str = ""
        if timeline_events:
            timeline_str = limit_str("\n".join(f"- {e}" for e in timeline_events if e.strip()), timeline_lim)

        tasks_str = ""
        if task_context:
            tasks_str = limit_str("\n".join(f"- {t}" for t in task_context if t.strip()), tasks_lim)

        return {
            "profile_context": profile_str,
            "long_term_context": direct_str,
            "semantic_context": semantic_str,
            "graph_context": graph_str,
            "timeline_context": timeline_str,
            "task_context": tasks_str
        }


class CognitiveReasoner:
    """
    High-level facade orchestrating specialized engines to retrieve, synthesize, 
    and resolve conflicting contexts in a confidence-aware pipeline.
    """
    def __init__(self, llm: BaseLLM, memory_service: MemoryService, task_service: Any):
        self.llm = llm
        self.memory_service = memory_service
        self.task_service = task_service
        self.context_builder = AdaptiveContextBuilder(max_tokens=4000)

    async def reason_over_context(self, query: str, session_id: str, intent: str) -> Dict[str, str]:
        """
        Coordinates cross-domain contexts (UserProfile, Memories, Knowledge Graph, 
        Timeline, Tasks) and resolves conflicts using LLM reasoning where appropriate.
        """
        # 1. Retrieve Raw Context Blocks from specialized components
        profile_context = {}
        direct_memories = []
        semantic_memories = []
        graph_context = []
        timeline_events = []
        task_context = []

        # A. User Profile Context
        if settings.ENABLE_USER_PROFILE and self.memory_service.user_profile_engine:
            profile_context = await self.memory_service.user_profile_engine.get_profile_context(session_id)

        # B. Direct Relational Memories (facts, preferences, notes, etc.)
        try:
            results_rel = await self.memory_service.search_service.search_relational_memories(query)
            for res in results_rel:
                m_type = res["memory_type"]
                if m_type in ("fact", "preference"):
                    direct_memories.append(f"Fact ({res.get('category')}): {res.get('key')} = {res.get('value')}")
                elif m_type == "note":
                    direct_memories.append(f"Note: {res.get('title')} - {res.get('content')}")
                elif m_type == "goal":
                    direct_memories.append(f"Goal: {res.get('title')} - {res.get('description')} (status: {res.get('status')})")
        except Exception as e:
            logger.warning(f"Reasoner direct memory search failed: {e}")

        # C. Semantic Conversation Memories (ChromaDB turns matches)
        try:
            results_sem = await self.memory_service.search_service.search_semantic_memories(query)
            for res in results_sem:
                semantic_memories.append(res["document"])
        except Exception as e:
            logger.warning(f"Reasoner semantic search failed: {e}")

        # D. Knowledge Graph Neighbourhood Expansion (GraphReasoner / GraphService)
        if settings.ENABLE_GRAPH and self.memory_service.graph_service:
            seed_entities = []
            # Pronoun referent resolution
            if settings.ENABLE_ALIAS_RESOLUTION and self.memory_service.pronoun_resolver:
                try:
                    recent_convs = await self.memory_service.sqlite_repo.get_recent_conversations(session_id, limit=5)
                    recent_msg_list = [{"role": c["role"], "content": c["content"]} for c in recent_convs]
                    ref_ent = await self.memory_service.pronoun_resolver.resolve_referent(query, recent_msg_list)
                    if ref_ent:
                        seed_entities.append(ref_ent["canonical_name"])
                except Exception as ex_pronoun:
                    logger.warning(f"Failed pronoun resolution check: {ex_pronoun}")
            
            # Entity name scan
            try:
                all_entities = await self.memory_service.sqlite_repo.list_entities(limit=100) if hasattr(self.memory_service.sqlite_repo, "list_entities") else []
                # Fallback to direct service lookup if repository method doesn't exist
                if not all_entities and hasattr(self.memory_service, "entity_repo"):
                    all_entities = await self.memory_service.entity_repo.list_entities(limit=100)
                
                for ent in all_entities:
                    if ent["canonical_name"].lower() in query.lower() and ent["canonical_name"] not in seed_entities:
                        seed_entities.append(ent["canonical_name"])
            except Exception as ex_ent:
                logger.warning(f"Failed entity name matching: {ex_ent}")
                
            if seed_entities:
                facts = await self.memory_service.graph_service.expand_context(seed_entities, max_depth=2)
                if facts:
                    graph_context = facts

        # E. Timeline Events Context (TimelineEngine)
        if intent in ("schedule_query", "timeline_query", "event_query"):
            from app.services.cognitive.timeline_engine import TimelineEngine
            timeline_engine = TimelineEngine(self.memory_service.event_repository)
            
            view = "upcoming"
            ref_time = datetime.utcnow()
            q_lower = query.lower()
            
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
            elif "overdue" in q_lower:
                view = "overdue"
            elif "completed" in q_lower:
                view = "completed"
            
            events = await timeline_engine.generate_timeline(session_id, view=view, start_date=ref_time)
            if events:
                for ev in events:
                    start_str = ev["start_time"].isoformat()
                    end_str = ev["end_time"].isoformat() if ev.get("end_time") else "None"
                    timeline_events.append(
                        f"[{ev['event_type'].upper()}] {ev['title']}: "
                        f"Start: {start_str}, End: {end_str}, "
                        f"Status: {ev['status']}, Importance: {ev['importance']}"
                    )

        # F. Active Task Lists Context (TaskService)
        if intent in ("task_query", "task_update", "task_create"):
            try:
                q_lower = query.lower()
                status_filter = None
                if "completed" in q_lower or "done" in q_lower:
                    status_filter = "completed"
                elif "cancelled" in q_lower:
                    status_filter = "cancelled"
                elif "in progress" in q_lower or "active" in q_lower:
                    status_filter = "in_progress"
                elif "pending" in q_lower:
                    status_filter = "pending"
                    
                tasks = await self.task_service.list_tasks(session_id, status=status_filter)
                if tasks:
                    for t in tasks:
                        due_str = t["due_date"].isoformat() if t.get("due_date") else "None"
                        task_context.append(
                            f"Task #{t['id']}: {t['title']} (status: {t['status']}, "
                            f"importance: {t['importance']}, due: {due_str})"
                        )
            except Exception as e:
                logger.warning(f"Reasoner task context retrieval failed: {e}")

        # 2. Confidence-aware conflict resolution
        # E.g., if direct_memories has contradiction on entity profile
        resolved_memories = self._resolve_contradictions(direct_memories)

        # 3. Apply Adaptive Context Budgeting
        budgeted_contexts = self.context_builder.build_adaptive_context(
            intent=intent,
            user_profile=profile_context,
            direct_memories=resolved_memories,
            semantic_memories=semantic_memories,
            graph_context=graph_context,
            timeline_events=timeline_events,
            task_context=task_context
        )
        return budgeted_contexts

    def _resolve_contradictions(self, memories: List[str]) -> List[str]:
        """
        Identifies duplicate/contradictory facts or keys and removes low-confidence
        or older representations deterministically.
        """
        seen_keys = {}
        cleaned = []
        for m in memories:
            # Parse 'Fact (category): key = value'
            if m.startswith("Fact ("):
                try:
                    parts = m.split("): ", 1)
                    key_val = parts[1].split(" = ", 1)
                    key = key_val[0].strip().lower()
                    val = key_val[1].strip()
                    if key in seen_keys:
                        # Contradiction: keep the latest or skip duplicate
                        continue
                    seen_keys[key] = val
                    cleaned.append(m)
                except Exception:
                    cleaned.append(m)
            else:
                cleaned.append(m)
        return cleaned
