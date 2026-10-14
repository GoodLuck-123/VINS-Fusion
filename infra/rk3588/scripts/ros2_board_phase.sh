#!/usr/bin/env bash
set -euo pipefail
runtime=$(/usr/bin/python3 -c 'import json,os,pathlib; p=json.loads((pathlib.Path(os.environ["VINS_REMOTE_PAYLOAD"])/"plan.json").read_text()); print((pathlib.Path.home()/pathlib.Path(p["runtime"]).expanduser()).resolve())')
source "$runtime/runtime_env.sh"
export VINS_BOARD_RUNTIME="$runtime"
python3 "$VINS_REMOTE_PAYLOAD/run_board_trials.py"
