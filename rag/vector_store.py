# rag/vector_store.py
import os
import threading
# pyrefly: ignore [missing-import]
import chromadb
from rag.logger import log_event

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "rag", "chromadb_store")

class ChromaStore:
    _client = None
    _collection = None
    _lock = threading.Lock()
    
    @classmethod
    def get_client(cls):
        if cls._client is None:
            os.makedirs(DB_PATH, exist_ok=True)
            cls._client = chromadb.PersistentClient(path=DB_PATH)
        return cls._client
        
    @classmethod
    def get_collection(cls):
        if cls._collection is None:
            client = cls.get_client()
            cls._collection = client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
        return cls._collection
        
    @classmethod
    def add_chunks(cls, ids, embeddings, metadatas, documents):
        with cls._lock:
            collection = cls.get_collection()
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            log_event("CHUNKS_ADDED", {"count": len(ids)})
            
    @classmethod
    def delete_by_filepath(cls, filepath):
        with cls._lock:
            collection = cls.get_collection()
            try:
                # Delete chunks belonging to the file using metadata filter
                collection.delete(where={"file_path": filepath})
                log_event("CHUNKS_DELETED", {"file_path": filepath})
            except Exception as e:
                log_event("DELETE_ERROR", {"file_path": filepath, "error": str(e)})
                
    @classmethod
    def search(cls, query_embedding, top_k=5):
        with cls._lock:
            collection = cls.get_collection()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            return results
