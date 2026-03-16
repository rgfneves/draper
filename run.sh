#!/usr/bin/env bash
# Convenience wrapper — runs commands inside the .venv without needing to activate it.
#
# Usage:
#   ./run.sh pipeline --platform instagram --limit 50 --dry-run
#   ./run.sh dashboard
#   ./run.sh test
#   ./run.sh test tests/test_scoring.py

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

CMD="${1:-help}"
shift || true

case "$CMD" in
  pipeline)
    "$VENV/bin/python" -m pipeline.runner "$@"
    ;;
  dashboard)
    "$VENV/bin/streamlit" run "$SCRIPT_DIR/dashboard/app.py" "$@"
    ;;
  test)
    "$VENV/bin/pytest" "${@:-tests/}" -v
    ;;
  help|*)
    echo "Usage: ./run.sh [pipeline|dashboard|test] [args...]"
    echo ""
    echo "  pipeline  --platform instagram --limit 50 --dry-run"
    echo "  dashboard"
    echo "  test [path]"
    ;;
esac
