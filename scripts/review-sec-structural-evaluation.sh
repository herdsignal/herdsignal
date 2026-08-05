#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/data/.venv/bin/python}"

PYTHONPATH="$ROOT_DIR/data" "$PYTHON" \
  "$ROOT_DIR/data/herd/sec_8k_structural_evaluation_review_v1.py" "$@"
