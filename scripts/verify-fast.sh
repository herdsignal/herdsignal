#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] Backend action-boundary smoke tests"
(
  cd "$ROOT_DIR/backend"
  ./gradlew test \
    --tests com.herdsignal.config.SecurityConfigTest \
    --tests com.herdsignal.service.ActionAuthorityPolicyTest \
    --tests com.herdsignal.service.decision.ObjectiveEvidenceServiceTest
)

echo "[2/3] Frontend primary-flow smoke tests"
(
  cd "$ROOT_DIR/frontend"
  npm test -- \
    src/pages/Dashboard/Dashboard.test.jsx \
    src/pages/StockDetail/StockDetail.test.jsx \
    src/components/DataStatus/dataStatusModel.test.js
)

echo "[3/3] Research-boundary smoke tests"
if [[ -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/data/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi
"$PYTHON" "$ROOT_DIR/data/tools/environment_check.py"
"$PYTHON" "$ROOT_DIR/data/herd/research_artifact_catalog.py"
(
  cd "$ROOT_DIR"
  PYTHONPATH=data "$PYTHON" -m pytest -q \
    data/tests/test_current_state_audit.py \
    data/tests/test_research_decision_v4.py \
    data/tests/test_research_decision_v5.py \
    data/tests/test_sec_8k_material_event_review_batching_v1.py \
    data/tests/test_scheduler_completion_audit.py
)

echo "빠른 일상 검증을 통과했습니다. 배포·대규모 변경 전에는 ./scripts/verify.sh를 실행하세요."
