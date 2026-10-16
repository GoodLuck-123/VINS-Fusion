#!/usr/bin/env bash
set -euo pipefail
cd "$VINS_REMOTE_CWD"
exec /usr/bin/python3 -I "$VINS_REMOTE_PAYLOAD/shutdown_ab.py" \
  "$VINS_REMOTE_WORKSPACE/releases/ros1-v0.2/install" \
  "$VINS_REMOTE_WORKSPACE/validation/shutdown-fix/install" \
  "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" "$VINS_REMOTE_ROOT/logs"
