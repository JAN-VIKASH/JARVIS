"""
ChromaDB semantic repository for vector storage.
"""
from typing import List, Dict, Any
import chromadb
from app.config.settings import settings

class ChromaMemoryRepository:
    """
    Vector database repository wrapping the persistent ChromaDB client.
    """
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection("jarvis_memories")

    def save_embedding(
        self,
        memory_id: str,
        embedding: List[float],
        document: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Persists a text chunk alongside its pre-computed embedding vector.
        """
        self.collection.upsert(
            ids=[memory_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document]
        )

    def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs cosine distance search matching candidate embeddings.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )
        
        ret = []
        if not results or "ids" not in results or not results["ids"] or not results["ids"][0]:
            return ret
            
        ids = results["ids"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [1.0] * len(ids)
        documents = results["documents"][0] if "documents" in results and results["documents"] else [""] * len(ids)
        metadatas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(ids)
        
        for i in range(len(ids)):
            ret.append({
                "id": ids[i],
                "distance": distances[i],
                "document": documents[i],
                "metadata": metadatas[i]
            })
        return ret

    def delete_embedding(self, memory_id: str) -> None:
        """
        Deletes a vector record from ChromaDB.
        """
        try:
            self.collection.delete(ids=[memory_id])
        except Exception as e:
            # Shield vector errors to maintain fail-safe behavior
            pass

