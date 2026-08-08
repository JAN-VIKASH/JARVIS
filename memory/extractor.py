"""
MemoryExtractor class implementing rule-based patterns and LLM-based extraction.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from memory.llm_extractor import LLMMemoryExtractor
from app.config.settings import settings

logger = logging.getLogger("jarvis.memory")

class MemoryExtractor:
    """
    Extracts structured memories (category, key, value, type) from user inputs.
    Combines rule-based regex extraction with LLM-based structured extraction.
    """
    def __init__(self, llm_extractor: Optional[LLMMemoryExtractor] = None):
        self.llm_extractor = llm_extractor
        self.confidence_threshold = settings.REGEX_CONFIDENCE_THRESHOLD
        
        # Regex mappings for entity extraction
        # Each tuple is (pattern, memory_type, category, key_template, value_template)
        self.rules = [
            # Identity
            (r"\bmy name is ([\w\s\-']{2,30})\b", "fact", "identity", "name", r"\1"),
            (r"\bmy age is (\d+)\b", "fact", "identity", "age", r"\1"),
            (r"\bi am (\d+) years old\b", "fact", "identity", "age", r"\1"),
            (r"\bi live in ([\w\s,]{2,50})\b", "fact", "identity", "location", r"\1"),
            (r"\bi work as a ([\w\s]{2,50})\b", "fact", "identity", "occupation", r"\1"),
            (r"\bi work as an ([\w\s]{2,50})\b", "fact", "identity", "occupation", r"\1"),
            (r"\bmy occupation is ([\w\s]{2,50})\b", "fact", "identity", "occupation", r"\1"),
            
            # Birthday
            (r"\bmy birthday is ([\w\s\d]{2,30})\b", "fact", "personal", "birthday", r"\1"),
            
            # Preferences
            (r"\bmy (?:favorite|favourite) language is ([\w\s\-\+\#]{1,30})\b", "preference", "favorites", "favorite_language", r"\1"),
            (r"\bi like ([\w\s]{2,50})\b", "preference", "likes", r"\1", r"likes \1"),
            (r"\bi love ([\w\s]{2,50})\b", "preference", "likes", r"\1", r"loves \1"),
            (r"\bi prefer ([\w\s]{2,50})\b", "preference", "preferences", r"\1", r"prefers \1"),
            (r"\bmy favorite ([\w\s]+) is ([\w\s]{2,50})\b", "preference", "favorites", r"\1", r"favorite \1 is \2"),
            
            # Goals / Tasks / Notes
            (r"\bmy goal is to ([\w\s]{2,100})\b", "goal", "goals", r"\1", r"\1"),
            (r"\btask:\s*([\w\s]{2,100})\b", "task", "tasks", r"\1", r"\1"),
            (r"\bnote:\s*([\w\s,.-]{2,200})\b", "note", "notes", r"\1", r"\1"),
            (r"\bremember to ([\w\s,.-]{2,100})\b", "task", "tasks", r"\1", r"\1"),
        ]

    async def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Parses text and returns a list of extracted memory dictionaries using rule-based and/or LLM extraction.
        """
        extracted = []
        if not text:
            return extracted
            
        clean_text = text.strip()
        
        # 1. Regex rule matcher (Stage 1)
        regex_memories = []
        for pattern, m_type, category, key_tpl, val_tpl in self.rules:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                try:
                    key_str = match.expand(key_tpl).strip().lower().replace(" ", "_")
                    val_str = match.expand(val_tpl).strip()
                    
                    regex_memories.append({
                        "type": m_type,
                        "category": category,
                        "key": key_str,
                        "value": val_str,
                        "confidence": 1.0,  # Regex exact matches default to 1.0 confidence
                        "raw_text": f"{category.capitalize()} - {key_str}: {val_str}"
                    })
                except Exception:
                    continue
                    
        # Explicit remember requests check
        remember_match = re.search(r"\bremember this:\s*(.+)$", clean_text, re.IGNORECASE)
        if remember_match:
            val = remember_match.group(1).strip()
            regex_memories.append({
                "type": "note",
                "category": "explicit_request",
                "key": "remembered_fact",
                "value": val,
                "confidence": 1.0,
                "raw_text": f"Explicit memory: {val}"
            })
            
        # 2. Check if LLM extraction fallback is required and appropriate
        # Criteria: Rule extractor returns nothing OR returns memories below the confidence threshold
        max_confidence = max([m["confidence"] for m in regex_memories]) if regex_memories else 0.0
        
        if (not regex_memories or max_confidence < self.confidence_threshold) and self.llm_extractor:
            # Check if the message is likely to contain memory to minimize API calls
            if self._is_likely_memory(clean_text):
                logger.info(f"Regex extraction confidence low ({max_confidence}). Invoking LLMMemoryExtractor...")
                try:
                    llm_memories = await self.llm_extractor.extract(clean_text)
                    # Merge results safely
                    return self._merge_extracted_memories(regex_memories, llm_memories)
                except Exception as e:
                    # Fault-Tolerant fallback to RegexExtractor results only
                    logger.error(f"LLMMemoryExtractor failed: {e}. Falling back to RegexExtractor results.")
                    return regex_memories
            else:
                logger.debug("Message does not contain memory indicators. Skipping LLM extraction.")
                return regex_memories
                
        return regex_memories

    def _is_likely_memory(self, text: str) -> bool:
        """
        Heuristic filter to check if text contains memory candidate signals.
        """
        text_lower = text.lower().strip()
        keywords = {
            "my", "remember", "goal", "task", "note", "birthday",
            "hobby", "job", "occupation", "born", "age", "location",
            "hobbies", "likes", "dislikes", "learn", "teach", "favorite", "favourite"
        }
        if any(kw in text_lower for kw in keywords):
            return True
            
        # Pronoun + verb assertion check (allowing words in between, e.g. "I really prefer")
        pronouns = {"i", "me", "we", "us"}
        verbs = {"am", "work", "live", "like", "love", "prefer", "hate", "want", "need"}
        
        words = set(re.findall(r'\b\w+\b', text_lower))
        if pronouns.intersection(words) and verbs.intersection(words):
            return True
            
        return False

    def _merge_extracted_memories(self, regex_list: List[Dict[str, Any]], llm_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Safely merges regex and LLM results. If both extract the same key, keeps the higher-confidence version.
        """
        merged_dict = {}
        
        # Add regex results first
        for item in regex_list:
            key_unique = (item["type"], item["category"], item["key"])
            merged_dict[key_unique] = item
            
        # Add LLM results, checking for conflicts
        for item in llm_list:
            key_unique = (item["type"], item["category"], item["key"])
            if key_unique in merged_dict:
                # If key already exists, keep the higher confidence one
                if item["confidence"] > merged_dict[key_unique]["confidence"]:
                    merged_dict[key_unique] = item
            else:
                merged_dict[key_unique] = item
                
        return list(merged_dict.values())
