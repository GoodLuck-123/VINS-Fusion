#!/usr/bin/env bash
set -euo pipefail
test "$(cat "$VINS_REMOTE_PAYLOAD/value.txt")" = 'remote workflow smoke'
printf 'payload verified; intentional exit 7\n' > "$VINS_REMOTE_ROOT/logs/probe.txt"
exit 7
