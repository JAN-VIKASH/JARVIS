import re

class ResponsePostProcessor:
    """
    Cleans up LLM generated responses to eliminate filler, repetition, and redundant endings.
    Supports both chunk-level and full-response cleaning.
    """
    @staticmethod
    def clean_chunk(chunk: str) -> str:
        """
        Modularity helper to clean or preprocess individual streaming chunks.
        Currently handles double spacing, formatting, or casing cleanup.
        """
        if not chunk:
            return ""
        return re.sub(r"\s+", " ", chunk)

    @staticmethod
    def process(text: str, intent: str = "conversation") -> str:
        """
        Cleans the full completed response text.
        """
        if not text:
            return ""
            
        cleaned = text.strip()
        
        # 1. Deduplicate/reduce repetitive "sir"
        # Keep at most one "sir" per response
        sir_count = len(re.findall(r"\bsir\b", cleaned, re.IGNORECASE))
        if sir_count > 1:
            # Keep only the first "sir" and replace others
            parts = re.split(r"(\bsir\b)", cleaned, flags=re.IGNORECASE)
            new_parts = []
            found_first = False
            for part in parts:
                if part.lower() == "sir":
                    if not found_first:
                        new_parts.append(part)
                        found_first = True
                else:
                    new_parts.append(part)
            cleaned = "".join(new_parts)

        # Clean double spaces or comma spacing caused by replacing sir
        cleaned = re.sub(r",\s*,", ",", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        
        # 2. Eliminate common repetitive polite/helper follow-ups or endings at the very end
        removable_endings = [
            r"Would you like me to.*",
            r"How may I assist you today\??",
            r"Is there anything else I can help (you )?with\??",
            r"Is there anything else you need help with\??",
            r"How else can I help you\??",
            r"Let me know if you need anything else\."
        ]
        
        # We only remove endings if the intent doesn't genuinely require them
        if intent in ("memory_recall", "memory_update", "simple_fact_question", "coding_help", "explanation"):
            for pattern in removable_endings:
                cleaned = re.sub(pattern + r"\s*$", "", cleaned, flags=re.IGNORECASE).strip()

        # 3. Deduplicate identical sentences
        sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        seen_sentences = set()
        unique_sentences = []
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            s_norm = re.sub(r'[^\w\s]', '', s_clean.lower())
            if s_norm in seen_sentences:
                continue
            seen_sentences.add(s_norm)
            unique_sentences.append(s)
            
        cleaned = " ".join(unique_sentences).strip()
        
        # Fix punctuation spaces (e.g. "foo , bar" -> "foo, bar")
        cleaned = re.sub(r'\s+([.!?,])', r'\1', cleaned)
        return cleaned
