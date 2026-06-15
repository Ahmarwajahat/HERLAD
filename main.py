from dotenv import load_dotenv
load_dotenv()

import os, threading, json, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from agent.brain import run_agent
from rag import start_watcher_thread

OWNER = os.getenv("MY_WHATSAPP_NUMBER", "923430699325")
PENDING_FILE = "logs/pending_tasks.json"
agent_busy = False

class TaskHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global agent_busy
        if self.path == '/task':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                task = data.get('task', '').strip()
                sender = data.get('from', '')
                
                if not task:
                    self.send_response(400)
                    self.end_headers()
                    return
                
                # Check for stop or restart keywords (can be executed even when agent is busy)
                if task.lower() == 'stop':
                    print(f"[System]: Stop command received from {sender}!")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'STOPPED')
                    
                    # 1. Kill active python execution processes and browser processes
                    import subprocess
                    try:
                        subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "firefox"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "local_exec"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "task1.py"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "task2.py"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "task3.py"], capture_output=True)
                        subprocess.run(["pkill", "-9", "-f", "task4.py"], capture_output=True)
                    except Exception as pe:
                        print(f"[Stop Process Error]: {pe}")
                    
                    # 2. Reset pending tasks status to cancelled
                    if os.path.exists(PENDING_FILE):
                        try:
                            tasks = json.load(open(PENDING_FILE))
                            for t in tasks:
                                if t['status'] in ['pending', 'running']:
                                    t['status'] = 'cancelled'
                            json.dump(tasks, open(PENDING_FILE,'w'), indent=2)
                        except Exception as te:
                            print(f"[Stop Task Reset Error]: {te}")
                    
                    # 3. Reset agent busy flag
                    global agent_busy
                    agent_busy = False
                    
                    # 4. Notify user via WhatsApp
                    try:
                        from agent.tools.notifier import whatsapp_notify_me
                        if sender and sender != 'Dashboard':
                            os.environ["MY_WHATSAPP_NUMBER"] = sender
                        whatsapp_notify_me("🛑 HERALD stopped successfully. All background tasks killed, and agent is ready for your next prompt!")
                    except Exception as ne:
                        print(f"[Stop Notify Error]: {ne}")
                    return

                if task.lower() == 'restart':
                    print(f"[System]: Restart command received from {sender}!")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'RESTARTING')
                    
                    # Reset tasks status
                    if os.path.exists(PENDING_FILE):
                        try:
                            tasks = json.load(open(PENDING_FILE))
                            for t in tasks:
                                if t['status'] in ['pending', 'running']:
                                    t['status'] = 'cancelled'
                            json.dump(tasks, open(PENDING_FILE,'w'), indent=2)
                        except:
                            pass
                            
                    # Notify user
                    try:
                        from agent.tools.notifier import whatsapp_notify_me
                        if sender and sender != 'Dashboard':
                            os.environ["MY_WHATSAPP_NUMBER"] = sender
                        whatsapp_notify_me("🔄 Restarting HERALD system service... Please wait 10-15 seconds for connection to be re-established.")
                    except:
                        pass
                        
                    # Trigger systemd service restart
                    import subprocess
                    subprocess.Popen(["systemctl", "--user", "restart", "herald.service"])
                    return

                if agent_busy:
                    print(f"[System]: Agent is busy. Rejecting concurrent task request: {task[:50]}")
                    self.send_response(409)
                    self.end_headers()
                    self.wfile.write(b'Busy')
                    return
                
                print(f"\n{'='*50}")
                print(f"[WhatsApp Task]: {task}")
                print(f"{'='*50}\n")
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
                
                # Run agent in background
                def run():
                    global agent_busy
                    agent_busy = True
                    if sender and sender != 'Dashboard':
                        os.environ["MY_WHATSAPP_NUMBER"] = sender
                    else:
                        os.environ["MY_WHATSAPP_NUMBER"] = "923430699325"
                    try:
                        run_agent(task)
                    finally:
                        agent_busy = False
                        mark_task_done(task)
                
                t = threading.Thread(target=run)
                t.daemon = True
                t.start()
                
            except Exception as e:
                print(f"[Handler Error]: {e}")
                self.send_response(500)
                self.end_headers()
    
    def log_message(self, format: str, *args):
        pass

def mark_task_done(task):
    try:
        if not os.path.exists(PENDING_FILE): return
        tasks = json.load(open(PENDING_FILE))
        for t in tasks:
            if t['task'] == task:
                t['status'] = 'done'
        json.dump(tasks, open(PENDING_FILE,'w'), indent=2)
    except: pass

def check_missed_tasks():
    """Run tasks that were pending/running when laptop was off"""
    global agent_busy
    try:
        if not os.path.exists(PENDING_FILE): return
        tasks = json.load(open(PENDING_FILE))
        pending = [t for t in tasks if t['status'] in ['pending', 'running']]
        if pending:
            print(f"\n[System]: Found {len(pending)} missed tasks!")
            for t in pending:
                if agent_busy:
                    print(f"[System]: Missed task postponed because agent is busy: {t['task'][:50]}")
                    continue
                print(f"[System]: Executing missed: {t['task'][:50]}")
                sender = t.get('from', '')
                if sender and sender != 'Dashboard':
                    os.environ["MY_WHATSAPP_NUMBER"] = sender
                else:
                    os.environ["MY_WHATSAPP_NUMBER"] = "923430699325"
                
                t['status'] = 'running'
                json.dump(tasks, open(PENDING_FILE,'w'), indent=2)
                agent_busy = True
                try:
                    run_agent(t['task'])
                finally:
                    agent_busy = False
                t['status'] = 'done'
                json.dump(tasks, open(PENDING_FILE,'w'), indent=2)
    except Exception as e:
        print(f"[System]: Error checking missed tasks: {e}")
class TaskServer(HTTPServer):
    allow_reuse_address = True

def start_listener():
    port = 5000
    try:
        server = TaskServer(('', port), TaskHandler)
        print(f"[System]: WhatsApp listener on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[System]: Port {port} busy or failed to bind: {e}")

def main():
    os.makedirs("logs", exist_ok=True)
    
    # Start background RAG file watcher
    print("[System]: Starting RAG Knowledge Base watcher...")
    start_watcher_thread()
    time.sleep(1) # Let the initial sync print complete
    
    print("=" * 50)
    print("       HERALD Autonomous AI Agent")
    print("=" * 50)
    print(f"Owner: +{OWNER}")
    print("Send WhatsApp message to give tasks!")
    print("Or type manually below.")
    print("Type 'quit' to exit")
    print("=" * 50 + "\n")
    
    # Start WhatsApp listener
    listener = threading.Thread(target=start_listener)
    listener.daemon = True
    listener.start()
    time.sleep(1)
    
    # Check for missed tasks (laptop was off)
    missed_thread = threading.Thread(target=check_missed_tasks)
    missed_thread.daemon = True
    missed_thread.start()
    
    # Manual input loop
    while True:
        try:
            task = input("Manual task: ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                print("HERALD shutting down.")
                break
            if task:
                run_agent(task)
                print("\n" + "="*50 + "\n")
        except EOFError:
            # Background running (nohup) has closed stdin, keep thread alive
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                break
        except KeyboardInterrupt:
            print("\nHERALD shutting down.")
            break

if __name__ == '__main__':
    main()
