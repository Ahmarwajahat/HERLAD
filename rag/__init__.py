# rag/__init__.py
from rag.retriever import retrieve_context
from rag.ingest import ingest_file, scan_and_ingest_directory
from rag.watcher import start_watcher_thread
