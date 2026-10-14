#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
workspace=$(dirname "$repo")
target=${1:-firefly@10.106.0.220}
payload=${2:-$workspace/.infra/rk3588/ros1-payload}
output=${3:-${VINS_PHASE_DIRECTORY:?Set phase directory or supply output}/board}
"$workspace/.infra/bin/vins-remote" "$target" "$payload" \
  --run "$repo/infra/rk3588/scripts/ros1_runtime_smoke.sh" --output "$output" --timeout 240
