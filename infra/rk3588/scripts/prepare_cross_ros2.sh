#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
workspace=$(dirname "$repo")
sdk="$workspace/.infra/rk3588/ros2"
test "$(uname -s)" = Linux && test "$(uname -m)" = x86_64
mkdir -p "$sdk"
docker build --platform linux/amd64 --tag vins-rk3588-cross:jammy \
  "$repo/infra/rk3588/cross"
docker image inspect vins-rk3588-cross:jammy > "$sdk/builder-image.json"
docker run --rm --platform linux/amd64 \
  --env VINS_HOST_UID="$(id -u)" --env VINS_HOST_GID="$(id -g)" \
  --volume "$sdk:/work" vins-rk3588-cross:jammy
"$workspace/.infra/bin/vins-remote" firefly@10.106.0.220 "$sdk/smoke" \
  --run "$repo/infra/rk3588/scripts/cross_smoke.sh" \
  --output "$workspace/results/rk3588/cross-smoke01" --timeout 60
