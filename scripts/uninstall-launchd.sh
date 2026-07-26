#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

for label in com.herdsignal.scheduler com.herdsignal.backend; do
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  rm -f "$LAUNCH_AGENTS/$label.plist"
done

echo "HerdSignal 자동 실행 등록을 해제했습니다. 서비스 데이터는 삭제하지 않았습니다."
