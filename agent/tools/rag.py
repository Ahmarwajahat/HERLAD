# agent/tools/rag.py
import os
import shutil
from rag.retriever import retrieve_context
from rag.ingest import ingest_file
from rag.logger import log_event

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")

os.makedirs(KB_DIR, exist_ok=True)

def search_knowledge_base(query: str, top_n: int = 3) -> str:
    """Search knowledge base (RAG) using ChromaDB and Sentence Transformers"""
    try:
        results = retrieve_context(query, top_k=top_n)
        if not results:
            return "No relevant documents found in the knowledge base."
            
        formatted_results = []
        for idx, r in enumerate(results):
            formatted_results.append(
                f"--- Source: {r['document_name']} (Similarity Score: {r['score']:.4f}) ---\n{r['chunk_text'].strip()}"
            )
        return "\n\n".join(formatted_results)
    except Exception as e:
        log_event("TOOL_SEARCH_ERROR", {"query": query, "error": str(e)})
        return f"Error searching knowledge base: {e}"

def add_file_to_knowledge_base(source_path: str) -> str:
    """Copy a file to the knowledge base folder and index it immediately"""
    if not os.path.exists(source_path):
        return f"Source file '{source_path}' does not exist."
        
    filename = os.path.basename(source_path)
    dest_path = os.path.join(KB_DIR, filename)
    
    try:
        shutil.copy(source_path, dest_path)
        # Index it immediately
        chunks_indexed = ingest_file(dest_path)
        return f"Successfully added '{filename}' to the knowledge base and indexed {chunks_indexed} chunks!"
    except Exception as e:
        log_event("TOOL_ADD_ERROR", {"source_path": source_path, "error": str(e)})
        return f"Error adding file to knowledge base: {e}"
