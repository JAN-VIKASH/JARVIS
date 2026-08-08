import re
import logging
from typing import List, Dict, Any, Optional
from app.database.repositories.entity_repository import EntityRepository

logger = logging.getLogger("jarvis.cognitive.resolution")

class PronounResolver:
    """
    Decodes ambiguous pronouns ("he", "she", "it", "this project", "that language")
    using past conversation context.
    """
    def __init__(self, entity_repo: EntityRepository):
        self.entity_repo = entity_repo
        self._status = "healthy"

    def get_status(self) -> str:
        return self._status

    async def resolve_referent(self, query: str, recent_messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Returns the resolved Entity dictionary if a pronoun matches a previously mentioned entity.
        """
        q_lower = query.lower().strip()
        
        # Check if the query contains common pronouns
        pronoun_patterns = [
            (r"\b(it|this|that|its)\b", None),  # generic object/project/tool
            (r"\b(he|him|his|she|her|they|them)\b", "person"),  # person
            (r"\b(this\s+project|that\s+project|the\s+project)\b", "project"),
            (r"\b(this\s+language|that\s+language|the\s+language)\b", "programming language"),
            (r"\b(this\s+tool|that\s+tool|the\s+tool)\b", "tool")
        ]
        
        matched_type = None
        has_pronoun = False
        
        for pat, ent_type in pronoun_patterns:
            if re.search(pat, q_lower):
                has_pronoun = True
                if ent_type:
                    matched_type = ent_type
                    break
                    
        if not has_pronoun:
            return None

        # Fetch recent entities to search for referents
        entities = await self.entity_repo.list_entities(limit=100)
        if not entities:
            return None
            
        # Scan messages from most recent to oldest
        for msg in reversed(recent_messages):
            content = msg.get("content", "").lower()
            
            # Find which entity name is mentioned in this message
            for ent in entities:
                # If a specific type is matched, filter by that type
                if matched_type and ent["entity_type"] != matched_type:
                    continue
                    
                name = ent["canonical_name"].lower()
                # Use word boundary search
                if re.search(rf"\b{re.escape(name)}\b", content):
                    logger.info(f"Resolved pronoun referent: '{ent['canonical_name']}' from conversation history.")
                    return ent
                    
        return None
