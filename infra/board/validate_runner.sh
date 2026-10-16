#!/usr/bin/env bash
set -euo pipefail
candidate="$VINS_REMOTE_WORKSPACE/validation/v02/install"
cd "$VINS_REMOTE_CWD"
exec /usr/bin/python3 -I "$VINS_REMOTE_PAYLOAD/verify_runner.py" "$candidate" "$VINS_REMOTE_ROOT/logs" \
  "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" ${VINS_V02_FULL:+--full}
