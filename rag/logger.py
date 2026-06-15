# rag/logger.py
import logging
import os
from datetime import datetime
from agent.memory import MONGO_AVAILABLE, db

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/rag.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RAG")

def log_event(event_type: str, data: dict):
    message = f"[{event_type}] {data}"
    logger.info(message)
    print(f"[RAG Logger]: {message}")
    
    if MONGO_AVAILABLE:
        try:
            db["rag_logs"].insert_one({
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now()
            })
        except Exception as e:
            logger.error(f"Failed to log to MongoDB: {e}")
