# rag/watcher.py
import os
import time
import json
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rag.ingest import ingest_file
from rag.vector_store import ChromaStore
from rag.logger import log_event
from agent.memory import MONGO_AVAILABLE, db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
META_FILE = os.path.join(PROJECT_ROOT, "logs", "kb_file_metadata.json")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".py", ".json"}

def get_file_metadata(filepath: str) -> dict:
    try:
        stat = os.stat(filepath)
        return {
            "mtime": stat.st_mtime,
            "size": stat.st_size
        }
    except Exception:
        return {}

class KBMetadataTracker:
    @classmethod
    def load_all(cls) -> dict:
        if MONGO_AVAILABLE:
            try:
                records = list(db["kb_metadata"].find())
                return {r["file_path"]: {"mtime": r["mtime"], "size": r["size"]} for r in records}
            except Exception as e:
                log_event("META_LOAD_MONGO_ERROR", {"error": str(e)})
                
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                log_event("META_LOAD_FILE_ERROR", {"error": str(e)})
        return {}

    @classmethod
    def save(cls, filepath: str, mtime: float, size: int):
        if MONGO_AVAILABLE:
            try:
                db["kb_metadata"].update_one(
                    {"file_path": filepath},
                    {"$set": {"mtime": mtime, "size": size, "updated_at": time.time()}},
                    upsert=True
                )
            except Exception as e:
                log_event("META_SAVE_MONGO_ERROR", {"filepath": filepath, "error": str(e)})
                
        try:
            os.makedirs(os.path.dirname(META_FILE), exist_ok=True)
            data = {}
            if os.path.exists(META_FILE):
                try:
                    with open(META_FILE, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass
            data[filepath] = {"mtime": mtime, "size": size}
            with open(META_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log_event("META_SAVE_FILE_ERROR", {"filepath": filepath, "error": str(e)})

    @classmethod
    def delete(cls, filepath: str):
        if MONGO_AVAILABLE:
            try:
                db["kb_metadata"].delete_one({"file_path": filepath})
            except Exception as e:
                log_event("META_DELETE_MONGO_ERROR", {"filepath": filepath, "error": str(e)})
                
        try:
            if os.path.exists(META_FILE):
                with open(META_FILE, "r") as f:
                    data = json.load(f)
                if filepath in data:
                    del data[filepath]
                    with open(META_FILE, "w") as f:
                        json.dump(data, f, indent=2)
        except Exception as e:
            log_event("META_DELETE_FILE_ERROR", {"filepath": filepath, "error": str(e)})

class KBWatchHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path
        ext = os.path.splitext(src_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            log_event("WATCHER_FILE_CREATED", {"filepath": src_path})
            time.sleep(1) # Wait for copying to complete
            try:
                ingest_file(src_path)
                meta = get_file_metadata(src_path)
                if meta:
                    KBMetadataTracker.save(src_path, meta["mtime"], meta["size"])
            except Exception as e:
                log_event("WATCHER_INGEST_ERROR", {"filepath": src_path, "error": str(e)})

    def on_modified(self, event):
        if event.is_directory:
            return
        src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path
        ext = os.path.splitext(src_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            meta = get_file_metadata(src_path)
            stored = KBMetadataTracker.load_all().get(src_path)
            if stored and stored.get("mtime") == meta.get("mtime") and stored.get("size") == meta.get("size"):
                return # No actual change
            
            log_event("WATCHER_FILE_MODIFIED", {"filepath": src_path})
            time.sleep(1) # Wait for file write to complete
            try:
                ingest_file(src_path)
                if meta:
                    KBMetadataTracker.save(src_path, meta["mtime"], meta["size"])
            except Exception as e:
                log_event("WATCHER_MODIFY_ERROR", {"filepath": src_path, "error": str(e)})

    def on_deleted(self, event):
        if event.is_directory:
            return
        src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path
        ext = os.path.splitext(src_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            log_event("WATCHER_FILE_DELETED", {"filepath": src_path})
            try:
                ChromaStore.delete_by_filepath(src_path)
                KBMetadataTracker.delete(src_path)
            except Exception as e:
                log_event("WATCHER_DELETE_ERROR", {"filepath": src_path, "error": str(e)})

class KBWatcher:
    def __init__(self):
        self.observer = Observer()
        os.makedirs(KB_DIR, exist_ok=True)
        
    def initial_sync(self):
        """Sync files on startup, checking for new, modified, or deleted files"""
        log_event("INITIAL_SYNC_START", {"directory": KB_DIR})
        stored_meta = KBMetadataTracker.load_all()
        
        current_files = []
        for root, _, files in os.walk(KB_DIR):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    current_files.append(os.path.join(root, file))
                    
        # Process new/modified
        for filepath in current_files:
            meta = get_file_metadata(filepath)
            stored = stored_meta.get(filepath)
            
            if not stored or stored.get("mtime") != meta.get("mtime") or stored.get("size") != meta.get("size"):
                log_event("INITIAL_SYNC_INGEST", {"filepath": filepath, "reason": "new_or_modified"})
                try:
                    ingest_file(filepath)
                    KBMetadataTracker.save(filepath, meta["mtime"], meta["size"])
                except Exception as e:
                    log_event("INITIAL_SYNC_ERROR", {"filepath": filepath, "error": str(e)})
                    
        # Process deleted
        for filepath in list(stored_meta.keys()):
            if filepath not in current_files:
                log_event("INITIAL_SYNC_DELETE", {"filepath": filepath, "reason": "deleted_from_disk"})
                try:
                    ChromaStore.delete_by_filepath(filepath)
                    KBMetadataTracker.delete(filepath)
                except Exception as e:
                    log_event("INITIAL_SYNC_DELETE_ERROR", {"filepath": filepath, "error": str(e)})
                    
        log_event("INITIAL_SYNC_COMPLETE", {"directory": KB_DIR})

    def run(self):
        self.initial_sync()
        event_handler = KBWatchHandler()
        self.observer.schedule(event_handler, path=KB_DIR, recursive=True)
        self.observer.start()
        log_event("WATCHER_STARTED", {"directory": KB_DIR})
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

def start_watcher_thread():
    watcher = KBWatcher()
    t = threading.Thread(target=watcher.run)
    t.daemon = True
    t.start()
    return watcher
