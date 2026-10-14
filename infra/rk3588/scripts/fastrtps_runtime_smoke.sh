#!/usr/bin/env bash
set -euo pipefail
runtime=${VINS_ARM_VERIFIED_RUNTIME:?Pass the previously accepted remote runtime path}
source "$runtime/runtime_env.sh"
export AMENT_PREFIX_PATH="$VINS_REMOTE_PAYLOAD/ros:$AMENT_PREFIX_PATH"
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/ros/lib:$LD_LIBRARY_PATH"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI
python3 - <<'PY'
import hashlib,json,os,pathlib
root=pathlib.Path(os.environ['VINS_REMOTE_PAYLOAD'])
for relative,expected in json.loads((root/'files.json').read_text()).items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected, relative
PY
python3 "$runtime/ros2_runtime_smoke.py"
