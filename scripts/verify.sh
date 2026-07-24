#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/6] Backend clean tests"
(cd "$ROOT_DIR/backend" && ./gradlew clean test)

echo "[2/6] Frontend tests"
(cd "$ROOT_DIR/frontend" && npm test -- --run)

echo "[3/6] Frontend lint"
(cd "$ROOT_DIR/frontend" && npm run lint)

echo "[4/6] Frontend production build"
(cd "$ROOT_DIR/frontend" && npm run build)

echo "[5/6] Python environment contract"
if [[ -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/data/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
else
  PYTHON="$(command -v python3)"
fi
"$PYTHON" "$ROOT_DIR/data/tools/environment_check.py"
"$PYTHON" "$ROOT_DIR/data/herd/research_artifact_catalog.py"

echo "[6/6] Python data-engine tests"
(cd "$ROOT_DIR" && HERD_TEST_PROFILE="${HERD_TEST_PROFILE:-full}" "$PYTHON" -m pytest -q)

echo "All verification checks passed."
