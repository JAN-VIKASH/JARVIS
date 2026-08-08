"""
Heuristic Importance Scorer for memory instances.
"""
import re

class ImportanceScorer:
    """
    Evaluates raw strings to calculate importance scoring (0-100).
    """
    def __init__(self):
        self.rules = [
            (r"\b(name|identity|who am i|my name is)\b", 95),
            (r"\b(birthday|born|age)\b", 90),
            (r"\b(project|work|code|job|occupation|career)\b", 85),
            (r"\b(preference|like|love|hate|favorite|prefer)\b", 70),
            (r"\b(phone|email|address|contact|location|live in)\b", 80),
            (r"\b(remember to|remind me to|todo|task)\b", 60),
            (r"\b(note:|task:|goal:)\b", 75),
            (r"\b(important|critical|secret|password|username)\b", 90),
        ]

    def score(self, text: str) -> int:
        """
        Calculates score metric based on keyword heuristics.
        """
        if not text:
            return 10
            
        clean_text = text.lower()
        max_score = 30  # Default baseline score for general observations
        
        for pattern, score_val in self.rules:
            if re.search(pattern, clean_text):
                if score_val > max_score:
                    max_score = score_val
                    
        # Length adjustment
        words = clean_text.split()
        if len(words) > 15:
            max_score = min(max_score + 5, 100)
            
        return max_score
