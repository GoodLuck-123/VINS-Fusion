#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
ROOT="$VINS_WORKSPACE_DIR"
cd "$ROOT"
mkdir -p .infra/bin .infra/downloads
if [[ ! -x .infra/bin/micromamba ]]; then
  curl --fail --location --retry 3 \
    https://micro.mamba.pm/api/micromamba/linux-64/2.9.0 \
    --output .infra/downloads/micromamba.tar.bz2
  python3 - <<'PY'
import tarfile
with tarfile.open('.infra/downloads/micromamba.tar.bz2') as archive:
    archive.extract('bin/micromamba', '.infra', filter='data')
PY
fi
if [[ ! -f .infra/ros1/conda-meta/history ]]; then
  .infra/bin/micromamba create -y -r "$ROOT/.infra/mamba" -p "$ROOT/.infra/ros1" \
    -f "$ROOT/ros1-linux-64.lock"
fi
UV_CACHE_DIR="$ROOT/.infra/uv-cache" uv sync --locked --python /usr/bin/python3.10
bash "$ROOT/scripts/download_baseline_assets.sh"
sha256sum --check baseline-assets.sha256
bash "$ROOT/scripts/build_ros1_baseline.sh"
