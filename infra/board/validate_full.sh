#!/usr/bin/env bash
set -euo pipefail
cd "$VINS_REMOTE_CWD"
exec /usr/bin/python3 -I "$VINS_REMOTE_PAYLOAD/verify_runner.py" \
  "$VINS_REMOTE_WORKSPACE/validation/v02/install" "$VINS_REMOTE_ROOT/logs" \
  "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" --full
