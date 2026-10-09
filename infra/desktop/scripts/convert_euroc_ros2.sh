#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
export UV_CACHE_DIR="$VINS_WORKSPACE_DIR/.infra/uv-cache"
if [[ ! -d "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy_ros2" ]]; then
  uv run --project "$VINS_DESKTOP_DIR" --locked rosbags-convert \
    --src "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy.bag" \
    --dst "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy_ros2" \
    --dst-version 8 --dst-typestore ros2_humble \
    --include-topic /cam0/image_raw /cam1/image_raw /imu0
fi
uv run --project "$VINS_DESKTOP_DIR" --locked python \
  "$VINS_DESKTOP_DIR/scripts/validate_bag_conversion.py" \
  "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy.bag" \
  "$VINS_WORKSPACE_DIR/data/euroc/MH_01_easy_ros2" \
  --output "$VINS_WORKSPACE_DIR/results/ros2/bag_conversion.json"
