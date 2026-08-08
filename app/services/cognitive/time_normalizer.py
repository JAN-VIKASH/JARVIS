import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest

logger = logging.getLogger("jarvis.cognitive")

class TimeNormalizer:
    """
    Normalizes relative and conversational time references into absolute datetimes.
    Features deterministic regex shortcuts and a structured LLM fallback.
    """
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm
        
    def normalize_regex(self, text: str, reference_time: datetime) -> Optional[datetime]:
        """
        Attempts to resolve quick conversational matches deterministically.
        """
        t = text.lower().strip()
        
        # Strip simple punctuation
        t = re.sub(r"[.,!?]", "", t)
        
        if t in ("today", "now", "current"):
            return reference_time
        elif t == "yesterday":
            return reference_time - timedelta(days=1)
        elif t == "tomorrow":
            return reference_time + timedelta(days=1)
            
        # Matches "X days ago"
        days_ago = re.match(r"^(\d+)\s+days?\s+ago$", t)
        if days_ago:
            days = int(days_ago.group(1))
            return reference_time - timedelta(days=days)
            
        # Matches "in X days"
        in_days = re.match(r"^in\s+(\d+)\s+days?$", t)
        if in_days:
            days = int(in_days.group(1))
            return reference_time + timedelta(days=days)
            
        # Matches "X weeks ago"
        weeks_ago = re.match(r"^(\d+)\s+weeks?\s+ago$", t)
        if weeks_ago:
            weeks = int(weeks_ago.group(1))
            return reference_time - timedelta(weeks=weeks)

        # Matches "in X weeks"
        in_weeks = re.match(r"^in\s+(\d+)\s+weeks?$", t)
        if in_weeks:
            weeks = int(in_weeks.group(1))
            return reference_time + timedelta(weeks=weeks)
            
        return None

    async def normalize(self, text: str, reference_time: datetime) -> datetime:
        """
        Converts text with relative date/time into absolute UTC datetime.
        """
        # Convert reference_time to naive UTC
        if reference_time.tzinfo is not None:
            reference_time = reference_time.astimezone(timezone.utc).replace(tzinfo=None)
            
        # 1. Try deterministic regex checks first
        resolved = self.normalize_regex(text, reference_time)
        if resolved:
            return resolved
            
        # 2. Call LLM for complex text if provider is available
        if self.llm:
            try:
                system_prompt = (
                    "You are a temporal normalizer for JARVIS, an AI assistant.\n"
                    f"Reference System Time: {reference_time.isoformat()} ({reference_time.strftime('%A')})\n\n"
                    "Your task is to parse the relative time phrase provided and return ONLY the absolute datetime "
                    "in ISO 8601 format (YYYY-MM-DDTHH:MM:SS) with no other words, punctuation, or formatting.\n"
                    "If the phrase doesn't contain a specific time, default to 09:00:00.\n"
                    "If you cannot resolve the phrase, return exactly the Reference System Time."
                )
                req = ChatRequest(message=f"Normalize this time phrase: \"{text}\"", session_id="time_norm_temp")
                res = await self.llm.generate_response(req, system_prompt=system_prompt)
                
                # Extract ISO timestamp from result
                clean_res = res.response.strip()
                # Basic ISO extraction regex
                match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", clean_res)
                if match:
                    return datetime.fromisoformat(match.group(1))
                else:
                    # Try parsing date-only YYYY-MM-DD
                    match_date = re.search(r"(\d{4}-\d{2}-\d{2})", clean_res)
                    if match_date:
                        return datetime.fromisoformat(f"{match_date.group(1)}T09:00:00")
            except Exception as e:
                logger.error(f"Failed to normalize time via LLM: {e}")
                
        # 3. Fallback to reference time on any failure
        return reference_time
