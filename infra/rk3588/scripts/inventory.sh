#!/usr/bin/env bash
set -euo pipefail
/usr/bin/python3 "$VINS_REMOTE_PAYLOAD/probe_board.py" > "$VINS_REMOTE_ROOT/logs/board.json"
