#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"

curl --fail --silent --show-error "$BACKEND_URL/actuator/health/liveness" >/dev/null
curl --fail --silent --show-error "$BACKEND_URL/actuator/health/readiness" >/dev/null
curl --fail --silent --show-error "$BACKEND_URL/api/system/data-status"
echo
echo "백엔드 생존·준비·데이터 상태 확인 완료"
