"""
MemoryFilter implementation to parse user messages and screen out trivial chatter.
"""
import re
import logging

logger = logging.getLogger("jarvis.memory")

class MemoryFilter:
    """
    Checks if a given user message contains information suitable for long-term memory.
    """
    def __init__(self):
        # Greetings and small talk lists (must match fully or as core phrases)
        self.greetings = {
            "hi", "hello", "hey", "yo", "good morning", "good afternoon",
            "good evening", "greetings", "whats up", "what's up", "sup", "hello jarvis", "hi jarvis"
        }
        self.small_talk = {
            "how are you", "how's it going", "how's life", "how is it going",
            "what are you doing", "nice to meet you", "thank you", "thanks", "how are you today"
        }
        
        # Keyword patterns that signal long-term memory value
        self.value_patterns = [
            # Identity
            r"\bmy name is\b", r"\bi am\s+\d+\s+years\b", r"\bi live in\b", r"\bi work as\b", r"\bmy occupation\b",
            # Preferences
            r"\bi like\b", r"\bi prefer\b", r"\bi love\b", r"\bi hate\b", r"\bmy favorite\b", r"\bprefer to\b",
            # Goals / Tasks
            r"\bmy goal is\b", r"\bi want to achieve\b", r"\bi plan to\b", r"\bremember to\b", r"\bremind me\b",
            r"\bdon't forget to\b", r"\btask:\b", r"\bnote:\b",
            # Explicit Remember Requests
            r"\bremember this\b", r"\bsave this\b", r"\bstore this\b", r"\bkeep in mind\b", r"\bmy birthday\b"
        ]

    def should_persist(self, text: str) -> bool:
        """
        Determines whether the text contains information worthy of long-term storage.
        """
        if not text:
            return False
            
        clean_text = text.lower().strip()
        # Remove common punctuation for exact checks
        clean_stripped = re.sub(r'[^\w\s]', '', clean_text).strip()
        
        # 1. Reject if it is a pure greeting
        if clean_stripped in self.greetings:
            logger.info("MemoryFilter: Rejected due to greeting match")
            return False
            
        # 2. Reject if it is pure small talk
        if clean_stripped in self.small_talk:
            logger.info("MemoryFilter: Rejected due to small talk match")
            return False
            
        # 3. Check value patterns
        for pattern in self.value_patterns:
            if re.search(pattern, clean_text):
                logger.info(f"MemoryFilter: Accepted via pattern match: {pattern}")
                return True
                
        # 4. Filter out simple questions / one-time search questions
        if clean_stripped.startswith(("what is", "where is", "when did", "how do i", "tell me a joke", "what time")):
            logger.info("MemoryFilter: Rejected due to one-time question prefix check")
            return False
            
        # 5. Check sentence length (very short messages are usually noise)
        words = clean_stripped.split()
        if len(words) < 3:
            logger.info("MemoryFilter: Rejected due to short word count (< 3)")
            return False
            
        # Default to False to keep memory clean unless it has clear characteristics
        logger.info("MemoryFilter: Rejected by default rule filter")
        return False
