#!/usr/bin/env bash
# Run the four archived ROS 1 trials serially, in separate ROS/evaluation shells.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
cd "$VINS_REPO_DIR"
batch="$VINS_WORKSPACE_DIR/results/ubuntu22-reproduction/ros1"
mkdir -p "$batch"
bash -c 'source infra/desktop/scripts/ros1_env.sh; python infra/desktop/scripts/verify_native_environment.py' > "$batch/native-check.log" 2>&1
UV_CACHE_DIR="$VINS_WORKSPACE_DIR/.infra/uv-cache" uv run --project "$VINS_DESKTOP_DIR" --locked python \
  infra/desktop/scripts/inspect_euroc.py "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy.bag" \
  --output "$VINS_WORKSPACE_DIR/results/ros1/MH_01_easy_bag.json" > "$batch/input-check.log" 2>&1
names=("$@")
if [[ ${#names[@]} == 0 ]]; then
  names=(native_MH01_baseline_r01 native_MH01_baseline_r02 native_MH01_metrics_r01 native_MH01_metrics_r02)
fi
for name in "${names[@]}"; do
  bash -c 'source infra/desktop/scripts/ros1_env.sh; python infra/desktop/scripts/run_euroc_baseline.py --rate 1 --name "$1"' _ "$name" > "$batch/$name.log" 2>&1
  UV_CACHE_DIR="$VINS_WORKSPACE_DIR/.infra/uv-cache" uv run --project "$VINS_DESKTOP_DIR" --locked python \
    infra/desktop/scripts/evaluate_baseline.py "$VINS_WORKSPACE_DIR/results/ros1/$name" > "$batch/$name-evaluation.log" 2>&1
  python3 - "$VINS_WORKSPACE_DIR/results/ros1/$name" "$VINS_WORKSPACE_DIR/results/ros1/MH_01_easy_bag.json" <<'PY'
import json
from pathlib import Path
import sys
run_dir, bag_path = map(Path, sys.argv[1:])
run = json.loads((run_dir / 'run.json').read_text())
evaluation = json.loads((run_dir / 'evaluation.json').read_text())
bag = json.loads(bag_path.read_text())
if not run['success'] or run['playback_exit_code'] != 0:
    raise RuntimeError('Incomplete playback')
if run['vins_exit_code'] != -6:
    raise RuntimeError('Unexpected ROS 1 shutdown behavior; inspect before continuing')
if abs(run['last_timestamp_ns'] - bag['last_sensor_header_timestamps_ns']['/cam0/image_raw']) > 1_000_000:
    raise RuntimeError('Trajectory does not cover the last image')
if run['trajectory_poses'] != 1831 or evaluation['matched_poses'] != 1819:
    raise RuntimeError('Unexpected trajectory coverage; inspect before continuing')
log = (run_dir / 'vins.log').read_text()
if 'failure detection' in log or 'throw img' in log:
    raise RuntimeError('Tracking reset or pairing drop')
(run_dir / 'validation.json').write_text(json.dumps({
    'complete_playback': True, 'last_image_covered': True,
    'tracking_resets_or_pairing_drops': False,
    'shutdown': 'original unjoined sync thread abort (-6)',
    'input_counts': {c['topic']: c['count'] for c in bag['connections']},
    'input_count_scope': 'bag records, not instrumented ROS 1 callback counters',
}, indent=2) + '\n')
PY
  sleep 10
done
