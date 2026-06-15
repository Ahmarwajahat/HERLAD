import requests
import os
import time
from dotenv import load_dotenv
load_dotenv()

BRIDGE_URL = "http://localhost:3001"
MY_NUMBER = os.getenv("MY_WHATSAPP_NUMBER", "923430699325")

def whatsapp_send(number: str, message: str) -> str:
    # Clean number — remove spaces, dashes, plus sign
    number = number.replace('+', '').replace('-', '').replace(' ', '')
    
    # Always use whatsapp_notify_me for owner's number
    MY_NUM = os.getenv("MY_WHATSAPP_NUMBER", "").replace('+','').replace('-', '').replace(' ', '')
    if number == MY_NUM or number == "":
        return whatsapp_notify_me(message)
    
    chunk_size = 2000
    if len(message) > chunk_size:
        chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]
        results = []
        for idx, chunk in enumerate(chunks):
            part_msg = f"[Part {idx+1}/{len(chunks)}]\n{chunk}"
            try:
                r = requests.post(f"{BRIDGE_URL}/send",
                    json={"number": number, "message": part_msg},
                    timeout=15)
                data = r.json()
                if not data.get("success"):
                    results.append(f"Part {idx+1} failed: {data.get('error')}")
                else:
                    results.append(f"Part {idx+1} sent")
            except Exception as e:
                results.append(f"Part {idx+1} error: {str(e)}")
            time.sleep(1)
        return ", ".join(results)
    
    try:
        r = requests.post(f"{BRIDGE_URL}/send",
            json={"number": number, "message": message},
            timeout=10)
        data = r.json()
        if data.get("success"):
            return f"Message sent to {number}"
        # If LID error, try notify_me as fallback
        if "LID" in str(data.get("error", "")):
            return whatsapp_notify_me(message)
        return f"Failed: {data.get('error')}"
    except Exception as e:
        return f"Bridge error: {str(e)}"

def whatsapp_notify_me(message: str) -> str:
    """Send notification to owner's WhatsApp"""
    MY_NUM = os.getenv("MY_WHATSAPP_NUMBER", "923430699325").replace('+', '').replace('-', '').replace(' ', '')
    
    chunk_size = 2000
    if len(message) > chunk_size:
        chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]
        results = []
        for idx, chunk in enumerate(chunks):
            part_msg = f"[HERALD Part {idx+1}/{len(chunks)}]\n{chunk}"
            sent = False
            for attempt in range(5):
                try:
                    r = requests.post(f"{BRIDGE_URL}/send",
                        json={"number": MY_NUM, "message": part_msg},
                        timeout=15)
                    data = r.json()
                    if data.get("success"):
                        results.append(f"Part {idx+1} sent")
                        sent = True
                        break
                    err_msg = data.get("error", "")
                    if "not connected" in err_msg.lower() or "getchat" in err_msg.lower():
                        time.sleep(4)
                        continue
                except:
                    time.sleep(4)
            if not sent:
                results.append(f"Part {idx+1} failed")
            time.sleep(1)
        return ", ".join(results)
        
    for attempt in range(5):
        try:
            r = requests.post(f"{BRIDGE_URL}/send",
                json={"number": MY_NUM, "message": f"[HERALD] {message}"},
                timeout=10)
            if not r.text or not r.text.strip():
                time.sleep(4)
                continue
            data = r.json()
            if data.get("success"):
                return f"Message sent to {MY_NUM}"
            err_msg = data.get("error", "")
            if "not connected" in err_msg.lower() or "getchat" in err_msg.lower():
                time.sleep(4)
                continue
            return f"Failed: {err_msg}"
        except Exception as e:
            time.sleep(4)
            continue
    return "Failed: WhatsApp notification could not be sent because bridge was not ready."

def whatsapp_get_messages() -> str:
    """Get unread WhatsApp messages"""
    try:
        r = requests.get(f"{BRIDGE_URL}/messages", timeout=10)
        data = r.json()
        msgs = data.get("messages", [])
        if not msgs:
            return "No new messages"
        result = []
        for m in msgs:
            result.append(
                f"From: {m['from']}\nMessage: {m['body']}\nID: {m['id']}"
            )
        return "\n---\n".join(result)
    except Exception as e:
        return f"Bridge error: {str(e)}"

def whatsapp_reply(number: str, message: str) -> str:
    """Reply to a WhatsApp message"""
    return whatsapp_send(number, message)

def whatsapp_status() -> str:
    """Check if WhatsApp bridge is connected"""
    try:
        r = requests.get(f"{BRIDGE_URL}/status", timeout=5)
        return r.json().get("status", "unknown")
    except:
        return "Bridge not running. Start with: cd whatsapp-bridge && node server.js"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def send_whatsapp_file(filepath: str, caption: str = "") -> str:
    MY_NUM = os.getenv("MY_WHATSAPP_NUMBER", "923430699325")
    MY_NUM = MY_NUM.replace("+", "").replace("-", "").strip()
    
    # Resolve path fallback if it doesn't exist
    if not os.path.exists(filepath):
        filename = os.path.basename(filepath)
        # Check logs directory
        logs_path = os.path.join(PROJECT_ROOT, "logs", filename)
        if os.path.exists(logs_path):
            filepath = logs_path
        else:
            # Check project tasks directory or project root
            tasks_path = os.path.join(PROJECT_ROOT, "tasks", filename)
            if os.path.exists(tasks_path):
                filepath = tasks_path
            else:
                root_path = os.path.join(PROJECT_ROOT, filename)
                if os.path.exists(root_path):
                    filepath = root_path
                    
    if not os.path.exists(filepath):
        return f"Error: File not found at {filepath}"
    
    for attempt in range(5):
        try:
            r = requests.post(
                f"{BRIDGE_URL}/send-file",
                json={
                    "number": MY_NUM,
                    "filepath": filepath,
                    "caption": caption or "Task complete — file attached"
                },
                timeout=30
            )
            
            # Handle empty response
            if not r.text or not r.text.strip():
                time.sleep(4)
                continue
            
            data = r.json()
            if data.get("success"):
                return f"File sent on WhatsApp: {filepath}"
            
            err_msg = data.get("error", "Unknown error")
            if "not connected" in err_msg.lower() or "getchat" in err_msg.lower():
                time.sleep(4)
                continue
                
            return f"Failed: {err_msg}"
            
        except requests.exceptions.JSONDecodeError:
            time.sleep(4)
            continue
        except requests.exceptions.ConnectionError:
            time.sleep(4)
            continue
        except Exception as e:
            return f"Error: {str(e)}"
            
    return "Failed: WhatsApp bridge was not ready or connected in time."
