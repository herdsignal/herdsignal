#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
failed=false

for label in com.herdsignal.backend com.herdsignal.scheduler com.herdsignal.backup com.herdsignal.weekly-report; do
  if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
    state="$(launchctl print "$DOMAIN/$label" | awk '/state =/{print $3; exit}')"
    pid="$(launchctl print "$DOMAIN/$label" | awk '/pid =/{print $3; exit}')"
    echo "$label: ${state:-unknown}${pid:+ (pid $pid)}"
  else
    echo "$label: 미등록"
    failed=true
  fi
done

if [[ "$failed" == true ]]; then
  exit 1
fi
