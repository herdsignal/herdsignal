#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/data/.venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

"$PYTHON" "$ROOT_DIR/data/tools/storage_audit.py" "$@"
