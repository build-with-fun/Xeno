#!/usr/bin/env bash
# install.sh — Set up the WhatsApp bot v2 from scratch.
#
# Usage:
#   ./scripts/install.sh          # install Python deps + Playwright Chromium
#   ./scripts/install.sh --dev    # also install pytest, mypy, etc.
#
set -euo pipefail

cd "$(dirname "$0")/.."
echo "=== WhatsApp Bot v2 — Installer ==="
echo "Project root: $(pwd)"
echo ""

# ── Check Python version ────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.11+ first."
    exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PY_VERSION"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "  OK - Python 3.11+ detected"
else
    echo "  FAIL - Python 3.11+ required (you have $PY_VERSION)"
    exit 1
fi
echo ""

# ── Create virtualenv (optional, recommended) ──────────────────────────────
if [ ! -d ".venv" ]; then
    echo "=== Creating virtualenv (.venv) ==="
    python3 -m venv .venv
    echo "  OK - Created .venv"
    echo ""
fi
# Activate for the rest of the script
# shellcheck disable=SC1091
source .venv/bin/activate
echo "Using virtualenv: $(which python)"
echo ""

# ── Install Python dependencies ────────────────────────────────────────────
echo "=== Installing Python dependencies ==="
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if [ "${1:-}" = "--dev" ]; then
    pip install pytest mypy ruff --quiet
    echo "  OK - Dev dependencies installed (pytest, mypy, ruff)"
fi
echo "  OK - Dependencies installed"
echo ""

# ── Install Playwright Chromium ─────────────────────────────────────────────
echo "=== Installing Playwright Chromium ==="
python -m playwright install chromium
python -m playwright install-deps 2>/dev/null || true
echo "  OK - Playwright Chromium installed"
echo ""

# ── Create .env from template ───────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "=== Creating .env from template ==="
    cp .env.example .env
    echo "  OK - Created .env - EDIT IT to add your API keys!"
else
    echo "=== .env already exists, skipping ==="
fi
echo ""

# ── Create runtime directories ──────────────────────────────────────────────
echo "=== Creating runtime directories ==="
mkdir -p data/{chats,pending,personas,alerts,analytics,retry,media_cache,whatsapp_session}
mkdir -p logs
echo "  OK - data/ and logs/ ready"
echo ""

# ── Verify installation ─────────────────────────────────────────────────────
echo "=== Verifying installation ==="
python -c "
import sys
sys.path.insert(0, '.')
try:
    from config import settings
    print('  OK - config module loads')
except Exception as e:
    print(f'  FAIL - config module: {e}')
    sys.exit(1)
try:
    from core.bot import Bot
    print('  OK - core.bot module loads')
except Exception as e:
    print(f'  FAIL - core.bot: {e}')
    sys.exit(1)
try:
    import playwright
    print('  OK - playwright installed')
except ImportError:
    print('  FAIL - playwright not installed')
    sys.exit(1)
try:
    import fastapi
    print('  OK - fastapi installed')
except ImportError:
    print('  FAIL - fastapi not installed')
    sys.exit(1)
print()
print('All checks passed!')
"
echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and fill in your API keys (at least one: GEMINI/GROQ/OPENAI)"
echo "  2. Set ADMIN_API_TOKEN to a long random string"
echo "  3. Run:      ./scripts/start.sh"
echo "  4. Scan the WhatsApp QR code on first run"
echo "  5. Admin API: http://127.0.0.1:5000/docs"
echo ""
