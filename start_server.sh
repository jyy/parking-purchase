#!/bin/bash
# Start python webserver in the background
python3 server.py &
SERVER_PID=$!

if [ -z "$TUNNEL_TOKEN" ]; then
    echo "No TUNNEL_TOKEN provided. Running local server only on port 8080."
    wait $SERVER_PID
else
    echo "Starting cloudflared tunnel..."
    cloudflared tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
fi
