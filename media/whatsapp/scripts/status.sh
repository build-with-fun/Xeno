#!/usr/bin/env bash
# status.sh — Check the bot's status via the admin API.
#
# Usage:
#   ./scripts/status.sh              # health + metrics + queue summary
#   ./scripts/status.sh --health     # just health
#   ./scripts/status.sh --pending    # just pending approvals
#
set -euo pipefail
cd "$(dirname "$0")/.."

# Load config
if [ -f ".env" ]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
fi

HOST="${ADMIN_HOST:-127.0.0.1}"
PORT="${ADMIN_PORT:-5000}"
TOKEN="${ADMIN_API_TOKEN:-}"
BASE="http://$HOST:$PORT"

AUTH_HEADER=""
if [ -n "$TOKEN" ] && [ "$TOKEN" != "change-this-to-a-long-random-string" ]; then
    AUTH_HEADER="Authorization: Bearer $TOKEN"
fi

api_get() {
    local path="$1"
    if [ -n "$AUTH_HEADER" ]; then
        curl -s -H "$AUTH_HEADER" "$BASE$path" 2>/dev/null
    else
        curl -s "$BASE$path" 2>/dev/null
    fi
}

format_json() {
    python3 -m json.tool 2>/dev/null || cat
}

case "${1:---all}" in
    --health)
        echo "=== Health Check ==="
        api_get "/api/health" | format_json
        ;;
    --metrics)
        echo "=== Metrics ==="
        api_get "/api/metrics" | format_json
        ;;
    --pending)
        echo "=== Pending Approvals ==="
        api_get "/api/pending" | format_json
        ;;
    --queue)
        echo "=== Full Queue ==="
        api_get "/api/queue" | format_json
        ;;
    --retry)
        echo "=== Retry Queue ==="
        api_get "/api/retry" | format_json
        ;;
    --analytics)
        echo "=== Analytics (7 days) ==="
        api_get "/api/analytics?days=7" | format_json
        ;;
    --all|*)
        echo "=== Bot Status ==="
        echo ""
        echo "--- Health ---"
        api_get "/api/health" | format_json
        echo ""
        echo "--- Pending Approvals ---"
        api_get "/api/pending" | format_json
        echo ""
        echo "--- Retry Queue ---"
        api_get "/api/retry" | format_json
        echo ""
        echo "--- Process Info ---"
        if [ -f "data/bot.pid" ]; then
            PID=$(cat data/bot.pid)
            if kill -0 "$PID" 2>/dev/null; then
                echo "  Bot PID: $PID (running)"
            else
                echo "  Bot PID: $PID (NOT running - stale PID file)"
            fi
        else
            echo "  No PID file (bot may be running in foreground)"
        fi
        ;;
esac
