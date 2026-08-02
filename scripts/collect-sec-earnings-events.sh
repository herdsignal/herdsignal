#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHONPATH=data data/.venv/bin/python -c \
  'import json; from scheduler.earnings_event_intake import collect_current_rush_earnings_events; print(json.dumps(collect_current_rush_earnings_events(), ensure_ascii=False, indent=2))'
