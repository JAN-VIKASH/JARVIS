import time
import re
from typing import Dict, Any, Optional

class ResponseCache:
    """
    Caches deterministic responses for memory recall and simple fact questions.
    TTL-based invalidation, plus explicit invalidation on updates.
    """
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        # Key: (session_id, query_normalized)
        # Value: {"response": str, "timestamp": float}
        self._cache: Dict[tuple, Dict[str, Any]] = {}
        
    def get(self, session_id: str, query: str) -> Optional[str]:
        q_norm = self._normalize_query(query)
        key = (session_id, q_norm)
        entry = self._cache.get(key)
        if entry:
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                return entry["response"]
            else:
                del self._cache[key]
        return None
        
    def set(self, session_id: str, query: str, response: str) -> None:
        q_norm = self._normalize_query(query)
        key = (session_id, q_norm)
        self._cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
        
    def invalidate_session(self, session_id: str) -> None:
        """
        Invalidates all cached entries for a given session.
        Useful when any memory is updated/deleted.
        """
        keys_to_del = [k for k in self._cache.keys() if k[0] == session_id]
        for k in keys_to_del:
            self._cache.pop(k, None)
            
    def _normalize_query(self, query: str) -> str:
        # Lowercase, strip punctuation and extra spacing
        q = query.lower().strip()
        q = re.sub(r'[^\w\s]', '', q)
        return " ".join(q.split())
