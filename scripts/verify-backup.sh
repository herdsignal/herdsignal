#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "사용법: ./scripts/verify-backup.sh backups/herdsignal-YYYYMMDD-HHMMSS.sql.gz" >&2
  exit 2
fi

BACKUP_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
CHECKSUM_PATH="$BACKUP_PATH.sha256"

[[ -f "$BACKUP_PATH" ]] || { echo "백업 파일이 없습니다: $BACKUP_PATH" >&2; exit 1; }
[[ -f "$CHECKSUM_PATH" ]] || { echo "체크섬 파일이 없습니다: $CHECKSUM_PATH" >&2; exit 1; }

gzip -t "$BACKUP_PATH"
if command -v shasum >/dev/null 2>&1; then
  (cd "$(dirname "$BACKUP_PATH")" && shasum -a 256 -c "$(basename "$CHECKSUM_PATH")")
else
  (cd "$(dirname "$BACKUP_PATH")" && sha256sum -c "$(basename "$CHECKSUM_PATH")")
fi

echo "백업 무결성 확인 완료: $BACKUP_PATH"
