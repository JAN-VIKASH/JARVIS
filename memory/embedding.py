"""
Offline-first Embedding Service using sentence-transformers.
"""
from typing import List
import logging
from collections import OrderedDict
from sentence_transformers import SentenceTransformer
from app.config.settings import settings

logger = logging.getLogger("jarvis.memory")

class EmbeddingService:
    """
    Computes semantic vector representations of text snippets.
    Enforces offline loading of configured models.
    """
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.cache_size = settings.EMBEDDING_CACHE_SIZE
        self.cache = OrderedDict()
        try:
            logger.info(f"Loading embedding model: {self.model_name} (local cache only)")
            # Enforce local files only to comply with offline-first design
            self.model = SentenceTransformer(self.model_name, local_files_only=True)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            msg = (
                f"Embedding model '{self.model_name}' could not be loaded from local cache. "
                "Runtime automatic downloads are disabled. Please download and cache the model "
                "weights offline first by executing the following terminal command:\n"
                "python -m voice.download_models"
            )
            logger.error(msg)
            raise RuntimeError(msg) from e

    def get_embeddings(self, text: str) -> List[float]:
        """
        Generates embedding vector list of float metrics. Utilizes an LRU cache.
        """
        if not text:
            return []
            
        # Check LRU cache
        if text in self.cache:
            self.cache.move_to_end(text)
            return self.cache[text]
            
        # Compute embedding
        embedding = self.model.encode(text).tolist()
        
        # Store in LRU cache
        self.cache[text] = embedding
        if len(self.cache) > self.cache_size:
            # Evict least recently used (first element)
            self.cache.popitem(last=False)
            
        return embedding

