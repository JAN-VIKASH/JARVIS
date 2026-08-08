import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.services.llm.base import BaseLLM
from app.models.chat_models import ChatRequest
from app.services.llm.generation_config import GenerationConfig

logger = logging.getLogger("jarvis.cognitive.graph")

class GraphExtractor:
    """
    Leverages LLM structured parser output to extract entities and relationships.
    """
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self._status = "healthy"
        self._extractions_count = 0

    def get_status(self) -> str:
        return self._status

    async def extract_graph(self, text: str) -> Dict[str, Any]:
        """
        Parses text and returns structural knowledge graph nodes and connections.
        """
        self._extractions_count += 1
        
        system_prompt = (
            "You are a knowledge graph extractor. Parse the input text and extract all relevant entities "
            "and their relationships. Output ONLY a valid JSON object matching this schema:\n\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "canonical entity name", "type": "person|project|skill|programming language|tool|organization|location|interest|goal|hobby", "description": "brief description", "confidence": 0.0-1.0}\n'
            "  ],\n"
            '  "relationships": [\n'
            '    {"source": "source entity name", "target": "target entity name", "type": "USES|WORKS_ON|LIKES|DISLIKES|LEARNS|STUDIES|KNOWS|OWNS|MEMBER_OF|PART_OF|CREATED|ATTENDS|LOCATED_IN|DEPENDS_ON|RELATED_TO", "confidence": 0.0-1.0, "weight": 0.0-5.0}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Do not output any thinking or conversational text.\n"
            "2. Ensure all fields are included in the JSON.\n"
            "3. Normalize entity types to the requested category keywords."
        )

        try:
            chat_req = ChatRequest(message=f"Text to extract:\n{text}")
            gen_config = GenerationConfig(temperature=0.0)  # low temp for deterministic JSON structure
            
            result = await self.llm.generate_response(
                request=chat_req,
                system_prompt=system_prompt,
                config=gen_config
            )
            
            resp_text = result.response.strip()
            
            # Clean markdown code blocks if any
            if resp_text.startswith("```"):
                resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
                resp_text = re.sub(r"\n```$", "", resp_text)
            
            parsed = json.loads(resp_text)
            
            # Basic validation check
            if "entities" not in parsed:
                parsed["entities"] = []
            if "relationships" not in parsed:
                parsed["relationships"] = []
                
            return parsed
            
        except Exception as e:
            logger.error(f"Failed graph extraction from text: {e}", exc_info=True)
            return {"entities": [], "relationships": []}
