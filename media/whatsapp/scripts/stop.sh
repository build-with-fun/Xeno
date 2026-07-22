#!/usr/bin/env bash
# stop.sh — Stop the running WhatsApp bot.
#
# Usage:
#   ./scripts/stop.sh          # graceful stop via stop-signal file
#   ./scripts/stop.sh --force  # force kill via SIGKILL
#
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = "--force" ]; then
    if [ -f "data/bot.pid" ]; then
        PID=$(cat data/bot.pid)
        echo "Force killing bot (PID $PID)..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f data/bot.pid
        echo "  Done."
    else
        echo "No PID file found. Trying to find python main.py process..."
        pkill -f "python main.py" && echo "  Killed." || echo "  No process found."
    fi
    exit 0
fi

# Graceful stop: touch the stop-signal file
echo "Sending graceful stop signal..."
mkdir -p data
touch data/STOP_SIGNAL
echo "  Stop signal file created. Bot will shut down within a few seconds."

# If we have a PID, wait for it
if [ -f "data/bot.pid" ]; then
    PID=$(cat data/bot.pid)
    echo "  Waiting for bot (PID $PID) to exit..."
    for i in $(seq 1 30); do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "  OK - Bot stopped."
            rm -f data/bot.pid data/STOP_SIGNAL
            exit 0
        fi
        sleep 1
    done
    echo "  WARN - Bot did not exit within 30s. Use --force to kill."
    exit 1
fi
