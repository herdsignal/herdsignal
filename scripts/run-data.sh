#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "루트 .env 파일이 없습니다. .env.example을 복사해 값을 채워주세요." >&2
  exit 1
fi

cd "$ROOT_DIR/data"
exec ./.venv/bin/python3.12 "$@"
