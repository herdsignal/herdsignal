#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/data/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

PYTHONPATH="$ROOT_DIR/data" "$PYTHON" "$ROOT_DIR/data/tools/current_state_audit.py"
