import logging
from typing import Optional, List, Dict, Any
from app.database.repositories.alias_repository import AliasRepository
from app.database.repositories.entity_repository import EntityRepository

logger = logging.getLogger("jarvis.cognitive.resolution")

def levenshtein_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()
    if s1 == s2:
        return 1.0
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    max_len = max(m, n)
    return 1.0 - (dp[m][n] / max_len)

class AliasResolutionEngine:
    """
    Resolves nickname/alias strings to canonical entity IDs using databases and Levenshtein edit distance.
    Uses an internal async cache to speed up lookups.
    """
    def __init__(self, alias_repo: AliasRepository, entity_repo: EntityRepository, cache_size: int = 128):
        self.alias_repo = alias_repo
        self.entity_repo = entity_repo
        self.cache = {}
        self.cache_keys = []
        self.cache_size = cache_size
        self._status = "healthy"
        self._resolutions_count = 0
        self._cache_hits = 0

    def get_status(self) -> str:
        return self._status

    def get_telemetry(self) -> Dict[str, Any]:
        hit_ratio = 0.0
        total_lookups = self._resolutions_count
        if total_lookups > 0:
            hit_ratio = self._cache_hits / total_lookups
        return {
            "alias_resolution_count": self._resolutions_count,
            "cache_hits": self._cache_hits,
            "cache_hit_ratio": hit_ratio
        }

    def clear_cache(self):
        self.cache.clear()
        self.cache_keys.clear()

    def invalidate_key(self, alias_text: str):
        norm = alias_text.strip().lower()
        if norm in self.cache:
            self.cache_keys.remove(norm)
            del self.cache[norm]

    def _set_cache(self, key: str, value: Optional[str]):
        if key in self.cache:
            self.cache_keys.remove(key)
        elif len(self.cache) >= self.cache_size:
            oldest = self.cache_keys.pop(0)
            del self.cache[oldest]
        self.cache[key] = value
        self.cache_keys.append(key)

    async def resolve_alias(self, alias_text: str, entity_type: Optional[str] = None) -> Optional[str]:
        """
        Attempts to resolve an entity name or alias to a canonical entity ID.
        """
        self._resolutions_count += 1
        norm = alias_text.strip().lower()
        
        # Check cache
        if norm in self.cache:
            self._cache_hits += 1
            return self.cache[norm]

        # 1. Exact alias match in DB
        alias_record = await self.alias_repo.find_alias(alias_text)
        if alias_record:
            entity_id = alias_record["entity_id"]
            self._set_cache(norm, entity_id)
            return entity_id

        # 2. Match directly by canonical name
        if entity_type:
            entity = await self.entity_repo.get_by_name(alias_text, entity_type)
            if entity:
                self._set_cache(norm, entity["id"])
                return entity["id"]

        # 3. Fuzzy search match on all entities (Levenshtein threshold 0.85)
        all_entities = await self.entity_repo.list_entities(limit=200)
        best_match = None
        best_score = 0.0
        
        for ent in all_entities:
            # Check type matching constraint if requested
            if entity_type and ent["entity_type"] != entity_type.strip().lower():
                continue
                
            score = levenshtein_similarity(alias_text, ent["canonical_name"])
            if score > best_score:
                best_score = score
                best_match = ent

        if best_score >= 0.85 and best_match:
            entity_id = best_match["id"]
            # Register this resolved alias in DB to speed up future matching
            try:
                await self.alias_repo.add_alias(
                    entity_id=entity_id,
                    alias=alias_text,
                    confidence=best_score,
                    source="fuzzy_engine"
                )
            except Exception as e:
                logger.warning(f"Failed to auto-persist resolved alias: {e}")
                
            self._set_cache(norm, entity_id)
            return entity_id

        # Not resolved
        self._set_cache(norm, None)
        return None
