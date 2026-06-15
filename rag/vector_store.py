# rag/vector_store.py
import os
import threading
import uuid
from typing import Any, Optional
# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from rag.logger import log_event

# Load environment variables if dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "rag", "qdrant_store")
COLLECTION_NAME = "knowledge_base"

class QdrantStore:
    _client: Optional[QdrantClient] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_client(cls) -> QdrantClient:
        if cls._client is None:
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            
            if qdrant_url:
                cls._client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
                print(f"[QdrantStore]: Connected to Qdrant server at {qdrant_url}")
            else:
                os.makedirs(DB_PATH, exist_ok=True)
                cls._client = QdrantClient(path=DB_PATH)
                print(f"[QdrantStore]: Initialized local Qdrant database at {DB_PATH}")
                
            # Ensure collection is initialized
            cls.get_collection()
        return cls._client
        
    @classmethod
    def get_collection(cls):
        client = cls._client
        if client is None:
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            
            if qdrant_url:
                client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
                cls._client = client
            else:
                os.makedirs(DB_PATH, exist_ok=True)
                client = QdrantClient(path=DB_PATH)
                cls._client = client
            
        try:
            collections_response = client.get_collections()
            collections = [col.name for col in collections_response.collections]
        except Exception as e:
            print(f"[QdrantStore]: Error listing collections: {e}")
            collections = []
            
        if COLLECTION_NAME not in collections:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            log_event("QDRANT_COLLECTION_CREATED", {"name": COLLECTION_NAME})
        return COLLECTION_NAME
        
    @classmethod
    def add_chunks(cls, ids, embeddings, metadatas, documents):
        with cls._lock:
            client = cls.get_client()
            collection = cls.get_collection()
            
            points = []
            for idx, (pt_id, embedding, meta, doc) in enumerate(zip(ids, embeddings, metadatas, documents)):
                # Qdrant requires UUIDs or integers as point IDs.
                # Generate a stable UUID based on the string ID to avoid duplicates.
                pt_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, pt_id))
                
                payload = dict(meta)
                payload["document_text"] = doc
                
                points.append(
                    PointStruct(
                        id=pt_uuid,
                        vector=embedding,
                        payload=payload
                    )
                )
            
            client.upsert(
                collection_name=collection,
                points=points
            )
            log_event("CHUNKS_ADDED", {"count": len(ids)})
            
    @classmethod
    def delete_by_filepath(cls, filepath):
        with cls._lock:
            client = cls.get_client()
            collection = cls.get_collection()
            try:
                # Delete points filtering by the payload's "file_path"
                client.delete(
                    collection_name=collection,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="file_path",
                                match=MatchValue(value=filepath)
                            )
                        ]
                    )
                )
                log_event("CHUNKS_DELETED", {"file_path": filepath})
            except Exception as e:
                log_event("DELETE_ERROR", {"file_path": filepath, "error": str(e)})
                
    @classmethod
    def search(cls, query_embedding, top_k=5):
        with cls._lock:
            client: Any = cls.get_client()
            collection = cls.get_collection()
            
            search_result = client.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=top_k
            )
            
            # Format results to match the structure expected by retriever.py:
            # {
            #   "ids": [[id1, id2, ...]],
            #   "metadatas": [[meta1, meta2, ...]],
            #   "documents": [[doc1, doc2, ...]],
            #   "distances": [[dist1, dist2, ...]]
            # }
            ids = []
            metadatas = []
            documents = []
            distances = []
            
            for res in search_result:
                ids.append(res.id)
                payload = res.payload or {}
                doc = payload.get("document_text", "")
                meta = {k: v for k, v in payload.items() if k != "document_text"}
                
                metadatas.append(meta)
                documents.append(doc)
                
                # Convert Qdrant cosine similarity score to distance for compatibility:
                # similarity = 1.0 - (distance / 2.0) -> distance = 2.0 * (1.0 - score)
                dist = 2.0 * (1.0 - res.score)
                distances.append(dist)
                
            return {
                "ids": [ids],
                "metadatas": [metadatas],
                "documents": [documents],
                "distances": [distances]
            }

# Maintain backward compatibility for files importing ChromaStore
ChromaStore = QdrantStore
