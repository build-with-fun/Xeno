#!/usr/bin/env bash
# start.sh — Start the WhatsApp bot.
#
# Usage:
#   ./scripts/start.sh          # start in foreground
#   ./scripts/start.sh --bg     # start in background (logs to logs/bot.log)
#
set -euo pipefail
cd "$(dirname "$0")/.."

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

# Check .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env not found. Run ./scripts/install.sh first."
    exit 1
fi

# Remove stale stop signal if present
rm -f data/STOP_SIGNAL

if [ "${1:-}" = "--bg" ]; then
    echo "Starting bot in background..."
    mkdir -p logs
    nohup python main.py >> logs/bot.log 2>&1 &
    PID=$!
    echo "$PID" > data/bot.pid
    echo "  Bot PID: $PID"
    echo "  Logs:    logs/bot.log"
    echo "  Stop:    ./scripts/stop.sh"
    echo ""
    echo "  Waiting for startup..."
    sleep 3
    if kill -0 "$PID" 2>/dev/null; then
        echo "  OK - Bot is running"
    else
        echo "  FAIL - Bot exited. Check logs/bot.log"
        exit 1
    fi
else
    echo "Starting bot in foreground (Ctrl+C to stop)..."
    exec python main.py
fi
