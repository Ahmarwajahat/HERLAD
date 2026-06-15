#!/bin/bash
PROJECT="/mnt/AhmarData/openwork_project"
LOG="$PROJECT/logs/startup.log"
mkdir -p "$PROJECT/logs"

echo "[$(date)] HERALD starting..." | tee -a $LOG

# Wait for internet connectivity first
echo "[$(date)] Waiting for internet connection..." | tee -a $LOG
for i in {1..30}; do
    if ping -c 1 -W 2 google.com >/dev/null 2>&1 || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        echo "[$(date)] ✅ Internet connected!" | tee -a $LOG
        break
    fi
    sleep 2
done

# Kill old processes cleanly without usage errors
lsof -t -i:3001 | xargs kill -9 2>/dev/null
lsof -t -i:5000 | xargs kill -9 2>/dev/null
lsof -t -i:5001 | xargs kill -9 2>/dev/null
lsof -t -i:5173 | xargs kill -9 2>/dev/null
pkill -9 -f "node server.js" 2>/dev/null
pkill -9 -f "main.py" 2>/dev/null
pkill -9 -f "vite" 2>/dev/null
pkill -9 -f "puppeteer/chrome" 2>/dev/null
sleep 2

# Clear locks
rm -rf "$PROJECT/whatsapp-bridge/.wwebjs_auth/session/.lock"
rm -rf "$PROJECT/whatsapp-bridge/.wwebjs_auth/session/SingletonLock"
rm -rf "/home/ahmar/Desktop/AhmarData/openwork_project/whatsapp-bridge/.wwebjs_auth/session/.lock"
rm -rf "/home/ahmar/Desktop/AhmarData/openwork_project/whatsapp-bridge/.wwebjs_auth/session/SingletonLock"

# Start bridge
echo "[$(date)] Starting bridge..." | tee -a $LOG
cd "$PROJECT/whatsapp-bridge"
nohup node server.js >> "$LOG" 2>&1 &
echo $! > "$PROJECT/logs/bridge.pid"

# Wait for bridge to start up (check status API)
echo "[$(date)] Waiting for bridge to run on port 3001..." | tee -a $LOG
for i in {1..15}; do
    if curl -s http://localhost:3001/status > /dev/null 2>&1; then
        echo "[$(date)] ✅ Bridge is online" | tee -a $LOG
        break
    fi
    sleep 2
done

# Start Python agent
echo "[$(date)] Starting agent..." | tee -a $LOG
cd "$PROJECT"
nohup /home/ahmar/.pyenv/versions/3.11.9/bin/python3 -u main.py >> "$LOG" 2>&1 &
echo $! > "$PROJECT/logs/agent.pid"

# Start React Dashboard
echo "[$(date)] Starting React dashboard..." | tee -a $LOG
cd "$PROJECT/dashboard"
nohup npm run dev >> "$LOG" 2>&1 &
echo $! > "$PROJECT/logs/dashboard.pid"

echo "[$(date)] ✅ HERALD fully started!" | tee -a $LOG
echo "Logs: tail -f $LOG"
