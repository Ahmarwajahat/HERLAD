# agent/memory.py
# To install MongoDB on Kali Linux:
# sudo apt update
# sudo apt install -y mongodb
# sudo systemctl start mongodb
# sudo systemctl enable mongodb
# Verify: mongo --eval "db.runCommand({connectionStatus:1})"

import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import socket
from urllib.parse import urlparse

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")

def is_mongo_port_open(url):
    try:
        clean_url = url
        if not clean_url.startswith("mongodb://") and not clean_url.startswith("mongodb+srv://"):
            clean_url = "mongodb://" + clean_url
        parsed = urlparse(clean_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 27017
        
        # Fast socket connection check with a 100ms timeout
        s = socket.create_connection((host, port), timeout=0.1)
        s.close()
        return True
    except Exception:
        return False

MONGO_AVAILABLE = False
db = None

if is_mongo_port_open(MONGO_URL):
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=1000)
        client.server_info()
        db = client["orion"]
        tasks_col = db["tasks"]
        logs_col = db["logs"]
        MONGO_AVAILABLE = True
        print("[Memory]: MongoDB connected")
    except Exception as e:
        print(f"[Memory]: MongoDB port open but connection failed: {e}")
else:
    print("[Memory]: MongoDB port is closed. Bypassing MongoDB connection attempt to avoid import delays.")


def log_task(user_prompt: str, status: str = "started") -> str:
    """Log a new task"""
    task_id = None
    if MONGO_AVAILABLE:
        try:
            task = {
                "prompt": user_prompt,
                "status": status,
                "started_at": datetime.now(),
                "completed_at": None,
                "tool_calls": [],
                "model_used": None
            }
            result = tasks_col.insert_one(task)
            task_id = str(result.inserted_id)
        except Exception:
            pass
    
    if not task_id:
        import json, time
        task_id = str(int(time.time()))
        os.makedirs("logs", exist_ok=True)
        task = {
            "id": task_id,
            "prompt": user_prompt,
            "status": status,
            "started_at": datetime.now().isoformat(),
            "tool_calls": []
        }
        try:
            with open("logs/tasks.json", "a") as f:
                f.write(json.dumps(task) + "\n")
        except Exception:
            pass

    # Send event to Node.js HTTP bridge for WebSocket broadcast
    try:
        import requests
        requests.post("http://localhost:3001/api/event", json={
            "type": "task_started",
            "data": {
                "id": task_id,
                "prompt": user_prompt,
                "status": status,
                "started_at": datetime.now().isoformat()
            }
        }, timeout=2)
    except Exception:
        pass

    return task_id

def log_tool_call(task_id: str, tool_name: str, 
                  args: dict, result: str) -> None:
    """Log a tool call for a task"""
    if MONGO_AVAILABLE:
        try:
            log = {
                "task_id": task_id,
                "tool": tool_name,
                "args": args,
                "result": result[:500] if result else "",
                "timestamp": datetime.now()
            }
            logs_col.insert_one(log)
            try:
                from bson.objectid import ObjectId
                tasks_col.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$push": {"tool_calls": tool_name}}
                )
            except Exception:
                tasks_col.update_one(
                    {"_id": task_id},
                    {"$push": {"tool_calls": tool_name}}
                )
        except Exception:
            pass
    else:
        import json
        try:
            os.makedirs("logs", exist_ok=True)
            log = {
                "task_id": task_id,
                "tool": tool_name,
                "result_preview": str(result)[:200] if result else "",
                "time": datetime.now().isoformat()
            }
            with open("logs/tool_calls.json", "a") as f:
                f.write(json.dumps(log) + "\n")
        except Exception:
            pass

    # Send event to Node.js HTTP bridge for WebSocket broadcast
    try:
        import requests
        requests.post("http://localhost:3001/api/event", json={
            "type": "tool_call",
            "data": {
                "task_id": task_id,
                "tool": tool_name,
                "args": args,
                "result_preview": str(result)[:200] if result else "",
                "time": datetime.now().isoformat()
            }
        }, timeout=2)
    except Exception:
        pass

def complete_task(task_id: str, model: str) -> None:
    """Mark task as complete"""
    if MONGO_AVAILABLE:
        try:
            try:
                from bson.objectid import ObjectId
                tasks_col.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": {
                        "status": "completed",
                        "completed_at": datetime.now(),
                        "model_used": model
                    }}
                )
            except Exception:
                tasks_col.update_one(
                    {"_id": task_id},
                    {"$set": {
                        "status": "completed",
                        "completed_at": datetime.now(),
                        "model_used": model
                    }}
                )
        except Exception:
            pass
    else:
        import json
        try:
            with open("logs/tasks.json", "a") as f:
                f.write(json.dumps({
                    "id": task_id,
                    "status": "completed",
                    "model": model,
                    "completed_at": datetime.now().isoformat()
                }) + "\n")
        except Exception:
            pass

    # Send event to Node.js HTTP bridge for WebSocket broadcast
    try:
        import requests
        requests.post("http://localhost:3001/api/event", json={
            "type": "task_completed",
            "data": {
                "id": task_id,
                "status": "completed",
                "model": model,
                "completed_at": datetime.now().isoformat()
            }
        }, timeout=2)
    except Exception:
        pass

def get_recent_tasks(limit: int = 10) -> list:
    """Get recent tasks for dashboard"""
    if MONGO_AVAILABLE:
        try:
            tasks = tasks_col.find().sort(
                "started_at", -1).limit(limit)
            return list(tasks)
        except Exception:
            pass
            
    import json
    tasks = []
    try:
        if os.path.exists("logs/tasks.json"):
            with open("logs/tasks.json", "r") as f:
                for line in f:
                    if line.strip():
                        tasks.append(json.loads(line))
            tasks.sort(key=lambda x: x.get("started_at", ""), reverse=True)
            return tasks[:limit]
    except Exception:
        pass
    return []
