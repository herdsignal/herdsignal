#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

backend_ready=false
for _ in {1..120}; do
  if curl --fail --silent http://localhost:8080/actuator/health >/dev/null 2>&1; then
    backend_ready=true
    break
  fi
  sleep 1
done
if [[ "$backend_ready" != true ]]; then
  echo "120초 안에 백엔드가 준비되지 않아 스케줄러를 시작하지 않았습니다." >&2
  exit 1
fi

exec "$ROOT_DIR/scripts/run-data.sh" scheduler/herd_scheduler.py
