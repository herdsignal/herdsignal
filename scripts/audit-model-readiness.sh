#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT_DIR/scripts/run-data.sh" scheduler/model_readiness_audit.py \
  --output "$ROOT_DIR/data/runtime/reports/model-readiness-latest.json" \
  "$@"
