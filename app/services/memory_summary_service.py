"""
MemorySummaryService coordinates dialogue summarization and database compression routines.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.settings import settings
from app.services.llm.base import BaseLLM
from memory.memory_service import MemoryService

logger = logging.getLogger("jarvis.memory")

class MemorySummaryService:
    """
    Coordinates conversation dialogue history summarization and failure-safe history compression.
    Depends on BaseLLM through Dependency Injection.
    """
    def __init__(self, llm: BaseLLM, memory_service: MemoryService):
        self.llm = llm
        self.memory_service = memory_service

    async def summarize_session_dialogue(self, session_id: str) -> str:
        """
        Fetches conversation history, calls LLM to generate a concise summary, 
        and saves it as a Note memory instance.
        """
        # Fetch recent exchanges (up to 50 logs)
        dialogues = await self.memory_service.sqlite_repo.get_recent_conversations(session_id, limit=50)
        if not dialogues:
            return "No conversation history found to summarize."

        # Reconstruct dialogue text
        formatted_dialogue = []
        for msg in dialogues:
            role_str = "User" if msg["role"] == "user" else "Assistant"
            formatted_dialogue.append(f"{role_str}: {msg['content']}")
            
        dialogue_text = "\n".join(formatted_dialogue)
        
        prompt = (
            "Please summarize the following conversation dialogue history. "
            "Keep the summary concise, factual, and focused on key preferences, "
            "user tasks, facts, or events discussed. Do not include headers, "
            "metadata, or intros. Return only the summary text:\n\n"
            f"{dialogue_text}\n\n"
            "Summary:"
        )
        
        summary_text = await self.llm.generate(prompt)
        summary_text = summary_text.strip()
        
        # Save summary as a Note memory
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        title = f"Summary of Session {session_id} - {timestamp}"
        await self.memory_service.sqlite_repo.save_note(
            title=title,
            content=summary_text,
            importance=50
        )
        
        logger.info(f"Summarized session dialogue for session {session_id} into note: '{title}'")
        return summary_text

    async def compress_session_history(self, session_id: str) -> Optional[str]:
        """
        Failure-safe conversation history compression.
        If history count exceeds COMPRESSION_THRESHOLD, summaries the oldest messages,
        saves the summary, and deletes the raw records.
        If LLM summarization fails, history is preserved intact.
        """
        # 1. Count conversation logs
        count = await self.memory_service.sqlite_repo.get_conversation_count(session_id)
        threshold = settings.COMPRESSION_THRESHOLD
        target = settings.COMPRESSION_TARGET
        
        if count <= threshold:
            return None
            
        to_prune = count - target
        logger.info(f"Session {session_id} conversation log count ({count}) exceeds threshold ({threshold}). Pruning oldest {to_prune} logs.")
        
        # 2. Fetch oldest to_prune logs
        oldest_logs = await self.memory_service.sqlite_repo.get_oldest_conversations(session_id, limit=to_prune)
        if not oldest_logs:
            return None
            
        # Reconstruct pruned dialogue text
        formatted_dialogue = []
        for msg in oldest_logs:
            role_str = "User" if msg["role"] == "user" else "Assistant"
            formatted_dialogue.append(f"{role_str}: {msg['content']}")
            
        dialogue_text = "\n".join(formatted_dialogue)
        
        prompt = (
            "Please generate a concise, factual summary of the following oldest dialogue history. "
            "Capture any user preferences, habits, goals, tasks, or temporal details. "
            "Return only the summary text without introduction:\n\n"
            f"{dialogue_text}\n\n"
            "Summary:"
        )
        
        # 3. Call LLM to generate summary (Failure point)
        try:
            summary_text = await self.llm.generate(prompt)
            summary_text = summary_text.strip()
            if not summary_text:
                raise ValueError("LLM generated an empty summary.")
        except Exception as e:
            logger.error(f"Failed to generate LLM summary for conversation compression: {e}. Aborting compression.")
            return None
            
        # 4. Save summary Note (must persist successfully first)
        try:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            title = f"Compressed Dialogue History Summary - {timestamp}"
            await self.memory_service.sqlite_repo.save_note(
                title=title,
                content=summary_text,
                importance=60
            )
        except Exception as e:
            logger.error(f"Failed to save summary note during conversation compression: {e}. Aborting compression.")
            return None
            
        # 5. Delete raw dialogue records permanently from SQLite
        try:
            log_ids = [m["id"] for m in oldest_logs]
            await self.memory_service.sqlite_repo.delete_conversations_by_ids(log_ids)
            logger.info(f"Successfully compressed and pruned {len(log_ids)} dialogue logs for session {session_id}.")
        except Exception as e:
            logger.critical(f"Critical inconsistency: Saved compression note but failed to delete logs: {e}")
            return None
            
        return summary_text
