#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
LABELS=(com.herdsignal.backend com.herdsignal.scheduler com.herdsignal.backup com.herdsignal.weekly-report)
installed_labels=()

cleanup_partial_install() {
  for label in "${installed_labels[@]}"; do
    launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  done
}
trap cleanup_partial_install ERR

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "루트 .env 파일이 없어 자동 실행을 등록할 수 없습니다." >&2
  exit 1
fi
if [[ ! -x "$ROOT_DIR/data/.venv/bin/python" ]]; then
  echo "data/.venv가 준비되지 않았습니다." >&2
  exit 1
fi
if ! command -v mariadb-dump >/dev/null 2>&1 && ! command -v mysqldump >/dev/null 2>&1; then
  echo "자동 백업에 mariadb-dump 또는 mysqldump가 필요합니다." >&2
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS" "$ROOT_DIR/runtime/logs"

for label in "${LABELS[@]}"; do
  template="$ROOT_DIR/config/launchd/$label.plist.template"
  target="$LAUNCH_AGENTS/$label.plist"
  sed "s|__ROOT_DIR__|$ROOT_DIR|g" "$template" > "$target"
  plutil -lint "$target" >/dev/null
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$target"
  installed_labels+=("$label")
done

trap - ERR
echo "HerdSignal 백엔드·스케줄러 자동 실행을 등록했습니다."
echo "상태 확인: ./scripts/launchd-status.sh"
