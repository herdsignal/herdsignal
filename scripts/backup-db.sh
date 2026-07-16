#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "루트 .env 파일이 없습니다." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_HOST:?DB_HOST가 필요합니다.}"
: "${DB_PORT:?DB_PORT가 필요합니다.}"
: "${DB_USER:?DB_USER가 필요합니다.}"
: "${DB_PASSWORD:?DB_PASSWORD가 필요합니다.}"
: "${DB_NAME:?DB_NAME이 필요합니다.}"

BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
if [[ "$BACKUP_DIR" != /* ]]; then
  BACKUP_DIR="$ROOT_DIR/$BACKUP_DIR"
fi
mkdir -p "$BACKUP_DIR"

if command -v mariadb-dump >/dev/null 2>&1; then
  DUMP_COMMAND=(mariadb-dump)
elif command -v mysqldump >/dev/null 2>&1; then
  DUMP_COMMAND=(mysqldump)
else
  echo "mariadb-dump 또는 mysqldump가 필요합니다." >&2
  exit 1
fi

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP_PATH="$BACKUP_DIR/herdsignal-$TIMESTAMP.sql.gz"
CHECKSUM_PATH="$BACKUP_PATH.sha256"

MYSQL_PWD="$DB_PASSWORD" "${DUMP_COMMAND[@]}" \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --single-transaction \
  --routines \
  --triggers \
  --default-character-set=utf8mb4 \
  "$DB_NAME" | gzip -9 > "$BACKUP_PATH"

gzip -t "$BACKUP_PATH"
if command -v shasum >/dev/null 2>&1; then
  (cd "$BACKUP_DIR" && shasum -a 256 "$(basename "$BACKUP_PATH")" > "$(basename "$CHECKSUM_PATH")")
else
  (cd "$BACKUP_DIR" && sha256sum "$(basename "$BACKUP_PATH")" > "$(basename "$CHECKSUM_PATH")")
fi

find "$BACKUP_DIR" -type f \( -name 'herdsignal-*.sql.gz' -o -name 'herdsignal-*.sql.gz.sha256' \) \
  -mtime "+$BACKUP_RETENTION_DAYS" -delete

echo "백업 완료: $BACKUP_PATH"
