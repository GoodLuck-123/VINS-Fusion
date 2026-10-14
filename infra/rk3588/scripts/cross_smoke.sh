#!/usr/bin/env bash
set -euo pipefail
test "$(uname -m)" = aarch64
test "$(cat "$VINS_REMOTE_PAYLOAD/build_host_arch")" = x86_64
ldd "$VINS_REMOTE_PAYLOAD/hello" > "$VINS_REMOTE_ROOT/logs/ldd.txt"
! grep -q 'not found' "$VINS_REMOTE_ROOT/logs/ldd.txt"
"$VINS_REMOTE_PAYLOAD/hello" > "$VINS_REMOTE_ROOT/logs/hello.txt"
grep -q 'AARCH64_CROSS_OK pointer_bytes=8' "$VINS_REMOTE_ROOT/logs/hello.txt"
uname -a > "$VINS_REMOTE_ROOT/logs/kernel.txt"
