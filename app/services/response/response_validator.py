import re
import logging
from typing import List

logger = logging.getLogger("jarvis")

class ResponseValidator:
    """
    Validates LLM-generated responses to ensure correctness, formatting constraints,
    length limits, and prompt leak prevention. Returns fallbacks on failures.
    """
    @staticmethod
    def validate(
        response: str,
        context_values: List[str],
        max_words: int,
        intent: str
    ) -> str:
        if not response or not response.strip():
            logger.warning("Empty response received. Applying fallback.")
            if intent == "memory_recall":
                return "I do not have that information in my memory."
            return "I am sorry, but I couldn't generate a response."

        # 1. Enforce configured word limits
        words = response.split()
        if len(words) > max_words:
            logger.warning(f"Response length ({len(words)} words) exceeded max ({max_words}). Truncating.")
            response = " ".join(words[:max_words]).strip()

        # 2. Block internal prompt/debug leaks
        leak_markers = [
            "memory context", "relevance:", "similarity:", "category:", "memory type:", 
            "[memory (", "chromadb", "sqlite record", "internal id", "system prompt", "instruction:"
        ]
        lower_response = response.lower()
        if any(marker in lower_response for marker in leak_markers):
            logger.warning("Internal prompt leak detected in response. Cleaning leak lines.")
            cleaned_lines = [
                line for line in response.splitlines()
                if not any(marker in line.lower() for marker in leak_markers)
            ]
            response = "\n".join(cleaned_lines).strip()
            if not response:
                return "I do not have that information in my memory."

        # 3. Memory Recall Validation: reject hallucinations and validate formatting
        if intent == "memory_recall":
            response_lower = response.lower()
            
            is_no_info = (
                "do not have that information" in response_lower or 
                "don't know" in response_lower or 
                "not known" in response_lower or
                "don't have that" in response_lower
            )
            
            if not is_no_info:
                if context_values:
                    found_value = False
                    for val in context_values:
                        val_str = str(val).strip().lower()
                        # Direct substring check
                        if val_str in response_lower:
                            found_value = True
                            break
                            
                        # Word-level intersection check to handle grammatical variations (e.g. "likes" vs "like")
                        val_words = [
                            w for w in re.findall(r"\b\w+\b", val_str)
                            if len(w) > 2 and w not in ["likes", "liked", "prefers", "preferred", "loves", "loved"]
                        ]
                        if val_words and all(w in response_lower for w in val_words):
                            found_value = True
                            break
                            
                    if not found_value:
                        logger.warning(f"Memory recall response hallucinated. Context values: {context_values}. Response: {response}. Applying fallback.")
                        return "I do not have that information in my memory."
                else:
                    logger.warning(f"Memory recall generated fact but context is empty. Response: {response}. Applying fallback.")
                    return "I do not have that information in my memory."

        return response
