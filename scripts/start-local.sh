#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_SCHEDULER=false
PIDS=()

if [[ "${1:-}" == "--with-scheduler" ]]; then
  WITH_SCHEDULER=true
elif [[ $# -gt 0 ]]; then
  echo "사용법: ./scripts/start-local.sh [--with-scheduler]" >&2
  exit 2
fi

cleanup() {
  trap - INT TERM EXIT
  if [[ ${#PIDS[@]} -gt 0 ]]; then
    kill "${PIDS[@]}" 2>/dev/null || true
    wait "${PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

"$ROOT_DIR/scripts/run-backend.sh" &
PIDS+=("$!")
"$ROOT_DIR/scripts/run-frontend.sh" &
PIDS+=("$!")

if [[ "$WITH_SCHEDULER" == true ]]; then
  echo "백엔드 준비 후 스케줄러를 시작합니다."
  backend_ready=false
  for _ in {1..60}; do
    if curl --fail --silent http://localhost:8080/actuator/health >/dev/null 2>&1; then
      backend_ready=true
      break
    fi
    sleep 1
  done
  if [[ "$backend_ready" != true ]]; then
    echo "60초 안에 백엔드가 준비되지 않아 스케줄러를 시작하지 않았습니다." >&2
    exit 1
  fi
  "$ROOT_DIR/scripts/run-scheduler.sh" &
  PIDS+=("$!")
fi

echo "HerdSignal 로컬 실행 중 — 종료: Ctrl+C"
echo "프론트 http://localhost:5173 | 백엔드 http://localhost:8080"

while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "프로세스 하나가 종료되어 전체 로컬 환경을 정리합니다." >&2
      exit 1
    fi
  done
  sleep 2
done
