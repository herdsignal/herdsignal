#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/4] Backend tests"
(cd "$ROOT_DIR/backend" && ./gradlew test)

echo "[2/4] Frontend tests"
(cd "$ROOT_DIR/frontend" && npm test -- --run)

echo "[3/4] Frontend lint"
(cd "$ROOT_DIR/frontend" && npm run lint)

echo "[4/4] Python data-engine tests"
if [[ -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/data/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
else
  PYTHON="$(command -v python3)"
fi
(cd "$ROOT_DIR/data" && "$PYTHON" -m unittest discover -s tests -p 'test_*.py')

echo "All verification checks passed."
