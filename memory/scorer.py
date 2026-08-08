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


class AdaptiveImportanceLearner:
    """
    Controlled scoring mechanism based on:
    - retrieval relevance (similarity distance/score)
    - repeated meaningful access (access count)
    - explicit user importance signals (query keywords)
    - existing importance
    
    Prevents runaway inflation by capping the maximum boost.
    """
    def __init__(self, heuristic_scorer: ImportanceScorer):
        self.heuristic_scorer = heuristic_scorer
        self.importance_keywords = [
            "remember", "crucial", "important", "essential", "never forget",
            "always keep in mind", "save this", "critical", "mandatory"
        ]

    def compute_adaptive_score(
        self,
        current_importance: int,
        access_count: int,
        relevance_score: float,
        user_query: str
    ) -> int:
        """
        Calculates adapted importance score. Bounded to prevent repeated automatic
        retrievals from pushing everything to 100.
        """
        boost = 0
        query_lower = user_query.lower()
        
        # 1. Explicit user importance signal
        explicit_signal = any(word in query_lower for word in self.importance_keywords)
        if explicit_signal:
            boost += 15

        # 2. Repeated meaningful access & relevance boost
        # We only boost if relevance is high (e.g. relevance_score > 0.6)
        if relevance_score > 0.6:
            # Relevancy component: up to +10
            relevance_boost = int(relevance_score * 10)
            
            # Access frequency component: capped at +15
            access_boost = min((access_count // 3) * 2, 15)
            
            boost += (relevance_boost + access_boost)
            
        new_importance = min(max(current_importance, current_importance + boost), 100)
        return new_importance
