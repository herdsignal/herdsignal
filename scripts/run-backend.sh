#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "루트 .env 파일이 없습니다. .env.example을 복사해 값을 채워주세요." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

# 일부 개발 도구가 사용하는 범용 DEBUG 값은 Spring Boot의 전역 debug 플래그로
# 자동 매핑된다. HerdSignal은 SPRING_DEBUG만 명시적인 서버 디버그 설정으로 쓴다.
unset DEBUG

cd "$ROOT_DIR/backend"
exec ./gradlew bootRun
