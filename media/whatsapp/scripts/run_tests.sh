#!/usr/bin/env bash
# run_tests.sh — Run the full test suite.
#
# Usage:
#   ./scripts/run_tests.sh              # run all tests
#   ./scripts/run_tests.sh --verbose    # verbose output
#   ./scripts/run_tests.sh --coverage   # with coverage report (needs pytest-cov)
#
set -euo pipefail
cd "$(dirname "$0")/.."

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "=== WhatsApp Bot v2 — Test Suite ==="
echo ""

# Ensure test dependencies
pip install pytest --quiet 2>/dev/null || true

VERBOSE=""
COVERAGE=0
for arg in "$@"; do
    case "$arg" in
        --verbose|-v) VERBOSE="-v" ;;
        --coverage)   COVERAGE=1 ;;
    esac
done

if [ "$COVERAGE" = "1" ]; then
    pip install pytest-cov --quiet 2>/dev/null || true
    python -m pytest tests/ $VERBOSE \
        --cov=. --cov-report=term-missing --cov-report=html:htmlcov \
        --cov-config=.coveragerc 2>/dev/null || \
    python -m pytest tests/ $VERBOSE --cov=. --cov-report=term-missing
else
    python -m pytest tests/ $VERBOSE || \
    python -m unittest discover -s tests $VERBOSE
fi

echo ""
echo "=== Tests complete ==="
