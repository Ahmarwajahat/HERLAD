#!/bin/bash
echo "Starting HERALD..."

# Kill any stuck ports
sudo kill -9 $(sudo lsof -t -i:3001) 2>/dev/null
sudo kill -9 $(sudo lsof -t -i:5000) 2>/dev/null
sudo kill -9 $(sudo lsof -t -i:8000) 2>/dev/null

echo "Ports cleared."
echo ""
echo "Now open 2 terminals:"
echo ""
echo "Terminal 1 (WhatsApp Bridge):"
echo "  cd whatsapp-bridge && node server.js"
echo ""
echo "Terminal 2 (HERALD Agent):"
echo "  python3 main.py"
