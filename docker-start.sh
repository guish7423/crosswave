#!/bin/bash
# CrossWave Production Start — runs CrossWave app + HQ bridge in one container
set -e

# Default ports
CW_PORT=${PORT:-9999}
HQ_PORT=${HQ_PORT:-13001}

# Start HQ bridge in background
echo "[docker-start] Starting HQ bridge on :$HQ_PORT ..."
cd /app/hq
python -m uvicorn server:app --host 0.0.0.0 --port $HQ_PORT &
HQ_PID=$!

# Start CrossWave main app
echo "[docker-start] Starting CrossWave on :$CW_PORT ..."
cd /app
python -m uvicorn app.main:app --host 0.0.0.0 --port $CW_PORT &
CW_PID=$!

# Trap for graceful shutdown
trap "kill $HQ_PID $CW_PID 2>/dev/null; exit" SIGTERM SIGINT

# Wait for either to exit
wait -n $HQ_PID $CW_PID

# If one exits, kill the other
kill $HQ_PID $CW_PID 2>/dev/null
exit 1
