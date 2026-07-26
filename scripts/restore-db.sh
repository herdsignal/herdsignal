#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ $# -ne 3 || "$2" != "--confirm-database" ]]; then
  echo "사용법: ./scripts/restore-db.sh <backup.sql.gz> --confirm-database <DB_NAME>" >&2
  exit 2
fi
[[ -f "$ENV_FILE" ]] || { echo "루트 .env 파일이 없습니다." >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_HOST:?DB_HOST가 필요합니다.}"
: "${DB_PORT:?DB_PORT가 필요합니다.}"
: "${DB_USER:?DB_USER가 필요합니다.}"
: "${DB_PASSWORD:?DB_PASSWORD가 필요합니다.}"
: "${DB_NAME:?DB_NAME이 필요합니다.}"

if [[ "$3" != "$DB_NAME" ]]; then
  echo "확인한 DB 이름이 실제 DB_NAME과 다릅니다." >&2
  exit 1
fi
if command -v mariadb >/dev/null 2>&1; then
  CLIENT=(mariadb)
elif command -v mysql >/dev/null 2>&1; then
  CLIENT=(mysql)
else
  echo "mariadb 또는 mysql 클라이언트가 필요합니다." >&2
  exit 1
fi

"$ROOT_DIR/scripts/verify-backup.sh" "$1"
echo "복원 전 현재 DB를 안전 백업합니다."
"$ROOT_DIR/scripts/backup-db.sh"

gunzip -c "$1" | MYSQL_PWD="$DB_PASSWORD" "${CLIENT[@]}" \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --default-character-set=utf8mb4 \
  "$DB_NAME"

echo "DB 복원 완료: $DB_NAME"
