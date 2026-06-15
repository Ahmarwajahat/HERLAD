# rag/embeddings.py
import os
import torch
from rag.logger import log_event

# Optimize for local execution and low memory footprint
os.environ["TOKENIZERS_PARALLELISM"] = "false"
torch.set_num_threads(1)

class EmbeddingGenerator:
    _model = None
    
    @classmethod
    def get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            log_event("LOADING_EMBEDDING_MODEL", {"model_name": "all-MiniLM-L6-v2"})
            # Force CPU usage to preserve RAM/GPU resources for local execution
            cls._model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            log_event("EMBEDDING_MODEL_LOADED", {"model_name": "all-MiniLM-L6-v2"})
        return cls._model
        
    @classmethod
    def get_embedding(cls, text: str) -> list:
        try:
            model = cls.get_model()
            embedding = model.encode(text, convert_to_numpy=True).tolist()
            return embedding
        except Exception as e:
            log_event("EMBEDDING_ERROR", {"text_preview": text[:50], "error": str(e)})
            raise e
            
    @classmethod
    def get_embeddings(cls, texts: list) -> list:
        if not texts:
            return []
        try:
            model = cls.get_model()
            embeddings = model.encode(texts, convert_to_numpy=True).tolist()
            return embeddings
        except Exception as e:
            log_event("BATCH_EMBEDDING_ERROR", {"count": len(texts), "error": str(e)})
            raise e
