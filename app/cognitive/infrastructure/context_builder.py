import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.cognitive.infrastructure")

class ContextBuilder:
    """
    Assembles prompt context blocks under a dynamic token budget.
    Ensures highest-priority content is preserved while enforcing constraints.
    Prioritization order:
      1. User Profile
      2. Direct Memory
      3. Semantic Memory
      4. Graph Expansion (Knowledge Graph)
      5. Timeline (Events/Calendar)
      6. Recent Conversation
      7. Session Summary
    """
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def build_context(
        self,
        user_profile: Optional[Dict[str, Any]] = None,
        direct_memories: Optional[List[str]] = None,
        semantic_memories: Optional[List[str]] = None,
        graph_context: Optional[List[str]] = None,
        timeline_events: Optional[List[str]] = None,
        recent_conversation: Optional[List[Dict[str, str]]] = None,
        session_summary: Optional[str] = None
    ) -> str:
        """
        Assembles and returns a token-budgeted prompt context block.
        """
        # Prioritized items with formatting headers
        sections = []

        # 1. User Profile
        if user_profile:
            profile_lines = []
            for k, v in user_profile.items():
                if isinstance(v, list):
                    v_str = ", ".join(map(str, v))
                elif isinstance(v, dict):
                    v_str = ", ".join(f"{dk}: {dv}" for dk, dv in v.items())
                else:
                    v_str = str(v)
                profile_lines.append(f"- {k.title()}: {v_str}")
            if profile_lines:
                sections.append((1, "User Profile Context:\n" + "\n".join(profile_lines)))

        # 2. Direct Memory
        if direct_memories:
            lines = [f"- {m}" for m in direct_memories if m.strip()]
            if lines:
                sections.append((2, "Direct Memories:\n" + "\n".join(lines)))

        # 3. Semantic Memory
        if semantic_memories:
            lines = [f"- {m}" for m in semantic_memories if m.strip()]
            if lines:
                sections.append((3, "Semantic Memories:\n" + "\n".join(lines)))

        # 4. Graph Expansion
        if graph_context:
            lines = [f"- {g}" for g in graph_context if g.strip()]
            if lines:
                sections.append((4, "Knowledge Graph Relations:\n" + "\n".join(lines)))

        # 5. Timeline
        if timeline_events:
            lines = [f"- {e}" for e in timeline_events if e.strip()]
            if lines:
                sections.append((5, "Calendar Timeline Events:\n" + "\n".join(lines)))

        # 6. Recent Conversation
        if recent_conversation:
            convo_lines = []
            for msg in recent_conversation:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                convo_lines.append(f"{role.upper()}: {content}")
            if convo_lines:
                sections.append((6, "Recent Chat History:\n" + "\n".join(convo_lines)))

        # 7. Session Summary
        if session_summary:
            sections.append((7, f"Session Summary: {session_summary}"))

        # Sort sections by priority index (ascending)
        sections.sort(key=lambda x: x[0])

        assembled_str = ""
        current_tokens = 0

        # Heuristic character-to-token converter: 1 token ~ 4 characters
        for priority, text in sections:
            block = f"\n\n=== {text} ==="
            block_tokens = len(block) // 4
            if current_tokens + block_tokens <= self.max_tokens:
                assembled_str += block
                current_tokens += block_tokens
            else:
                # Truncate if partial space available
                space_left = self.max_tokens - current_tokens
                if space_left > 50:  # only append if meaningful space is left
                    allowed_chars = space_left * 4
                    truncated_text = text[:allowed_chars] + "\n[Truncated due to token budget]"
                    assembled_str += f"\n\n=== {truncated_text} ==="
                break

        return assembled_str.strip()
