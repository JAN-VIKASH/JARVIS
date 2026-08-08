"""
LLMMemoryExtractor class that parses user inputs using the configured LLM provider.
"""
import re
import json
import logging
from typing import List, Dict, Any
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest
from app.config.settings import settings

logger = logging.getLogger("jarvis.memory")

class LLMMemoryExtractor:
    """
    Extracts structured memories (category, key, value, type, confidence) from text
    by querying the active LLM provider (Groq/OpenAI) and parsing the JSON response.
    """
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Queries the LLM provider to extract structured memories from a message.
        """
        if not text:
            return []

        system_prompt = (
            "You are a structured memory extraction agent for JARVIS, a personal AI assistant.\n"
            "Analyze the USER's input text and extract any long-term memories such as facts, preferences, "
            "goals, tasks, notes, or explicit requests to remember things.\n\n"
            "Ignore greetings, small talk, one-time questions, or conversational filler.\n\n"
            "You must return a raw JSON list of objects, with NO surrounding explanation or conversational text.\n"
            "Each object in the JSON list must have exactly the following structure:\n"
            "{\n"
            '  "type": "fact" | "preference" | "goal" | "task" | "note",\n'
            '  "category": "string (e.g. identity, likes, personal, goals, tasks, notes, favorites)",\n'
            '  "key": "snake_case string representing the specific attribute (e.g. favorite_color, name, liked_languages)",\n'
            '  "value": "string representing the fact or preference value (e.g. Java, Paris, red)",\n'
            '  "confidence": float between 0.0 and 1.0\n'
            "}\n\n"
            "If no long-term memories are present, return an empty array: []\n\n"
            "Format rule: Do not use markdown formatting blocks or surrounding markdown text. Return only the JSON."
        )

        try:
            req = ChatRequest(message=f"Extract memories from: \"{text}\"", session_id="extractor_temp")
            # Set a lower request timeout if supported, otherwise call generate_response
            result = await self.llm.generate_response(req, system_prompt=system_prompt)
            raw_response = result.response
            
            cleaned_json = self._clean_json(raw_response)
            if not cleaned_json:
                return []
                
            parsed = json.loads(cleaned_json)
            if isinstance(parsed, list):
                validated_memories = []
                for item in parsed:
                    if isinstance(item, dict) and "type" in item and "key" in item and "value" in item:
                        # Clean key name to lowercase snake case
                        key_clean = re.sub(r'\s+', '_', str(item["key"]).strip().lower())
                        category_clean = str(item.get("category", "general")).strip().lower()
                        validated_memories.append({
                            "type": str(item["type"]).strip().lower(),
                            "category": category_clean,
                            "key": key_clean,
                            "value": str(item["value"]).strip(),
                            "confidence": float(item.get("confidence", 0.9)),
                            "raw_text": f"{category_clean.capitalize()} - {key_clean}: {item['value']}"
                        })
                return validated_memories
            else:
                logger.warning(f"LLM extractor did not return a JSON list: {raw_response}")
                return []
        except Exception as e:
            logger.error(f"Error executing LLMMemoryExtractor: {e}", exc_info=True)
            return []

    def _clean_json(self, text: str) -> str:
        """
        Cleans LLM response text, stripping markdown tags and isolating JSON arrays.
        """
        text = text.strip()
        # Remove Markdown JSON block wrappers
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            
        # Isolate bounding bracket arrays
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and start < end:
            return text[start:end+1]
            
        return text
