import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest
from app.database.repositories.event_repository import EventRepository

logger = logging.getLogger("jarvis.cognitive")

class EventUpdateDetector:
    """
    Detects whether user input refers to an event lifecycle change (CREATE, UPDATE, CANCEL, POSTPONE, COMPLETE)
    and resolves the target matched_event_id.
    """
    def __init__(self, llm: BaseLLM, event_repository: Optional[EventRepository] = None):
        self.llm = llm
        self.event_repository = event_repository or EventRepository()

    async def detect(self, session_id: str, text: str) -> Dict[str, Any]:
        # 1. Fetch recently scheduled active events to match against
        candidates = []
        try:
            today = await self.event_repository.get_today_events(session_id)
            upcoming = await self.event_repository.get_upcoming_events(session_id, limit=20)
            seen_ids = set()
            for ev in today + upcoming:
                if ev["id"] not in seen_ids:
                    candidates.append({
                        "id": ev["id"],
                        "title": ev["title"],
                        "start_time": ev["start_time"].isoformat(),
                        "event_type": ev["event_type"],
                        "status": ev["status"]
                    })
                    seen_ids.add(ev["id"])
        except Exception as e:
            logger.error(f"Failed to fetch candidates in EventUpdateDetector: {e}")

        # 2. Build LLM prompt to classify operation and resolve reference
        system_prompt = (
            "You are an event lifecycle update detector for JARVIS, an AI assistant.\n"
            "Analyze the USER's input text and classify if they are referencing one of the existing planned events "
            "listed below to update, cancel, postpone, or complete it, or if they are scheduling a new event.\n\n"
            "List of Existing Planned Events:\n"
            f"{json.dumps(candidates, indent=2)}\n\n"
            "Analyze the text and classify into one of the following operations:\n"
            "- CREATE: The user is scheduling or mentioning a brand new event not listed in the existing events.\n"
            "- UPDATE: The user is modifying details (like time, title, description) of an existing event.\n"
            "- CANCEL: The user is cancelling or deleting an existing event.\n"
            "- POSTPONE: The user is rescheduling/postponing an existing event to a future time.\n"
            "- COMPLETE: The user is marking an existing event as completed or finished.\n\n"
            "You must return a raw JSON object containing exactly the following structure with NO markdown block wrappers:\n"
            "{\n"
            '  "operation": "CREATE" | "UPDATE" | "CANCEL" | "POSTPONE" | "COMPLETE",\n'
            '  "matched_event_id": "string representing the ID of the matched event from the candidates, or null",\n'
            '  "confidence": float between 0.0 and 1.0\n'
            "}\n\n"
            "Format rule: Do not use markdown JSON block wrappers. Return only the JSON."
        )

        try:
            req = ChatRequest(message=f"Analyze input: \"{text}\"", session_id="update_detector_temp")
            res = await self.llm.generate_response(req, system_prompt=system_prompt)
            raw = res.response.strip()
            
            # Clean markdown wrappers if any
            match = re.search(r"({.*})", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
                
            parsed = json.loads(raw)
            return {
                "operation": str(parsed.get("operation", "CREATE")).strip().upper(),
                "matched_event_id": parsed.get("matched_event_id"),
                "confidence": float(parsed.get("confidence", 0.8))
            }
        except Exception as e:
            logger.error(f"Error in EventUpdateDetector: {e}")
            return {
                "operation": "CREATE",
                "matched_event_id": None,
                "confidence": 0.5
            }
