import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest
from app.services.cognitive.time_normalizer import TimeNormalizer

logger = logging.getLogger("jarvis.cognitive")

class EventExtractor:
    """
    Identifies calendar events, meetings, milestones, goals, and deadlines from conversations
    and extracts structured metadata details (title, type, start_time, end_time, etc.).
    """
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.time_normalizer = TimeNormalizer(llm)

    async def extract_events(self, text: str, reference_time: datetime) -> List[Dict[str, Any]]:
        if not text:
            return []
            
        system_prompt = (
            "You are an event extraction subagent for JARVIS, an AI assistant.\n"
            f"Reference System Time: {reference_time.isoformat()} ({reference_time.strftime('%A')})\n\n"
            "Analyze the USER's input and identify any specific current, past, or future events, meetings, "
            "appointments, deadlines, milestones, or scheduled activities.\n\n"
            "Ignore general facts, preferences, or conversation logs that do not refer to structured calendar/timeline events.\n\n"
            "You must return a raw JSON list of event objects, with NO surrounding explanation or markdown block wrappers.\n"
            "Each object in the JSON list must have exactly the following structure:\n"
            "{\n"
            '  "title": "string (e.g. Sync meeting with Jan, Project Deadline, Go to Gym)",\n'
            '  "description": "string (additional details or null)",\n'
            '  "event_type": "meeting" | "milestone" | "deadline" | "task" | "personal",\n'
            '  "start_time_phrase": "string representing the event\'s start date/time (e.g. tomorrow at 3pm, next Friday, yesterday)",\n'
            '  "end_time_phrase": "string representing the end date/time, or null if not specified",\n'
            '  "is_all_day": boolean,\n'
            '  "importance": "low" | "medium" | "high",\n'
            '  "confidence": float between 0.0 and 1.0\n'
            "}\n\n"
            "If no timeline events are present, return an empty array: []\n\n"
            "Format rule: Do not use markdown JSON block wrappers. Return only the JSON."
        )

        try:
            req = ChatRequest(message=f"Extract events from: \"{text}\"", session_id="extractor_temp")
            res = await self.llm.generate_response(req, system_prompt=system_prompt)
            raw_response = res.response.strip()
            
            cleaned_json = self._clean_json(raw_response)
            if not cleaned_json:
                return []
                
            parsed = json.loads(cleaned_json)
            if not isinstance(parsed, list):
                logger.warning(f"EventExtractor response was not a list: {raw_response}")
                return []
                
            extracted_events = []
            for item in parsed:
                if isinstance(item, dict) and "title" in item and "start_time_phrase" in item:
                    start_phrase = item["start_time_phrase"]
                    start_dt = await self.time_normalizer.normalize(start_phrase, reference_time)
                    
                    end_dt = None
                    end_phrase = item.get("end_time_phrase")
                    if end_phrase:
                        end_dt = await self.time_normalizer.normalize(end_phrase, reference_time)
                        
                    extracted_events.append({
                        "title": str(item["title"]).strip(),
                        "description": item.get("description"),
                        "event_type": str(item.get("event_type", "personal")).strip().lower(),
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "is_all_day": bool(item.get("is_all_day", False)),
                        "importance": str(item.get("importance", "medium")).strip().lower(),
                        "confidence": float(item.get("confidence", 0.8)),
                        "raw_text": text
                    })
            return extracted_events
        except Exception as e:
            logger.error(f"Error executing EventExtractor: {e}", exc_info=True)
            return []

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and start < end:
            return text[start:end+1]
            
        return text
