#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
logs="$VINS_REMOTE_ROOT/logs"
uname -a > "$logs/kernel.txt"
ldd "$VINS_REMOTE_PAYLOAD/legacy_smoke" > "$logs/ldd.txt"
! grep -q 'not found' "$logs/ldd.txt"
"$VINS_REMOTE_PAYLOAD/legacy_smoke" > "$logs/legacy_smoke.txt" 2> "$logs/stderr.txt"
grep -q 'ARM_LEGACY_OK opencv=4.2.0 ceres=1.14.0' "$logs/legacy_smoke.txt"
