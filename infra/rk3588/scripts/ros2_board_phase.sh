#!/usr/bin/env bash
set -euo pipefail
runtime=$(/usr/bin/python3 -c 'import json,os,pathlib; p=json.loads((pathlib.Path(os.environ["VINS_REMOTE_PAYLOAD"])/"plan.json").read_text()); print((pathlib.Path.home()/pathlib.Path(p["runtime"]).expanduser()).resolve())')
source "$runtime/runtime_env.sh"
export VINS_BOARD_RUNTIME="$runtime"
addon=$(/usr/bin/python3 -c 'import json,os,pathlib; p=json.loads((pathlib.Path(os.environ["VINS_REMOTE_PAYLOAD"])/"plan.json").read_text()); print((pathlib.Path.home()/pathlib.Path(p["ros_addon"]).expanduser()).resolve() if p.get("ros_addon") else "")')
if [[ -n "$addon" ]]; then
  export VINS_BOARD_ROS_ADDON="$addon"
  export AMENT_PREFIX_PATH="$addon/ros:$AMENT_PREFIX_PATH"
  export LD_LIBRARY_PATH="$addon/ros/lib:$LD_LIBRARY_PATH"
fi
python3 "$VINS_REMOTE_PAYLOAD/run_board_trials.py"
