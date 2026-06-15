# rag/retriever.py
from rag.embeddings import EmbeddingGenerator
from rag.vector_store import ChromaStore
from rag.logger import log_event

def retrieve_context(query: str, top_k: int = 5) -> list:
    """
    Retrieve most relevant chunks from ChromaDB for a given query.
    Returns list of dicts: [
        {
            "document_name": str,
            "file_path": str,
            "chunk_text": str,
            "chunk_id": str,
            "score": float
        }
    ]
    """
    try:
        log_event("RETRIEVAL_START", {"query": query, "top_k": top_k})
        
        # 1. Convert query to embedding
        query_embedding = EmbeddingGenerator.get_embedding(query)
        
        # 2. Search ChromaDB
        results = ChromaStore.search(query_embedding, top_k=top_k)
        
        # 3. Format results
        formatted_results = []
        if results and 'ids' in results and results['ids'] and len(results['ids'][0]) > 0:
            ids = results['ids'][0]
            metadatas = results['metadatas'][0]
            documents = results['documents'][0]
            distances = results['distances'][0] if 'distances' in results else [0.0] * len(ids)
            
            for idx in range(len(ids)):
                meta = metadatas[idx]
                distance = distances[idx]
                # Cosine distance to similarity: similarity = 1.0 - (distance / 2.0)
                # Keep it bounded between 0 and 1
                similarity_score = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
                
                formatted_results.append({
                    "document_name": meta.get("document_name", ""),
                    "file_path": meta.get("file_path", ""),
                    "chunk_text": documents[idx] if idx < len(documents) else meta.get("chunk_text", ""),
                    "chunk_id": ids[idx],
                    "score": similarity_score
                })
                
        # Log retrieval results
        log_event("RETRIEVAL_RESULTS", {
            "query": query,
            "results_count": len(formatted_results),
            "top_scores": [round(r["score"], 4) for r in formatted_results]
        })
        
        return formatted_results
    except Exception as e:
        log_event("RETRIEVAL_ERROR", {"query": query, "error": str(e)})
        return []
