#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
mkdir -p "$VINS_WORKSPACE_DIR/.infra/bin" "$VINS_WORKSPACE_DIR/.infra/downloads"
if [[ ! -x "$VINS_WORKSPACE_DIR/.infra/bin/micromamba" ]]; then
  curl --fail --location --retry 3 https://micro.mamba.pm/api/micromamba/linux-64/2.9.0 \
    --output "$VINS_WORKSPACE_DIR/.infra/downloads/micromamba.tar.bz2"
  python3 - "$VINS_WORKSPACE_DIR/.infra" <<'PY'
import sys, tarfile
from pathlib import Path
root = Path(sys.argv[1])
with tarfile.open(root / 'downloads/micromamba.tar.bz2') as archive:
    archive.extract('bin/micromamba', root, filter='data')
PY
fi
if [[ ! -f "$VINS_WORKSPACE_DIR/.infra/ros2/conda-meta/history" ]]; then
  "$VINS_WORKSPACE_DIR/.infra/bin/micromamba" create -y \
    -r "$VINS_WORKSPACE_DIR/.infra/mamba" -p "$VINS_WORKSPACE_DIR/.infra/ros2" \
    -f "$VINS_DESKTOP_DIR/ros2-linux-64.lock"
fi
UV_CACHE_DIR="$VINS_WORKSPACE_DIR/.infra/uv-cache" uv sync \
  --project "$VINS_DESKTOP_DIR" --locked --python /usr/bin/python3.10
bash "$VINS_DESKTOP_DIR/scripts/download_baseline_assets.sh"
cd "$VINS_WORKSPACE_DIR"
sha256sum --check "$VINS_DESKTOP_DIR/baseline-assets.sha256"
if [[ ! -f .infra/downloads/vision_opencv-3.2.1.tar.gz ]]; then
  curl --fail --location --retry 3 \
    https://codeload.github.com/ros-perception/vision_opencv/tar.gz/refs/tags/3.2.1 \
    --output .infra/downloads/vision_opencv-3.2.1.tar.gz.part
  mv .infra/downloads/vision_opencv-3.2.1.tar.gz.part .infra/downloads/vision_opencv-3.2.1.tar.gz
fi
sha256sum --check "$VINS_DESKTOP_DIR/ros2-assets.sha256"
if [[ ! -f .infra/src/vision_opencv-3.2.1/.extracted ]]; then
  python3 - <<'PY'
import tarfile
from pathlib import Path
root = Path('.infra/src/vision_opencv-3.2.1')
root.mkdir(parents=True, exist_ok=True)
with tarfile.open('.infra/downloads/vision_opencv-3.2.1.tar.gz') as archive:
    for member in archive.getmembers():
        member.name = '/'.join(member.name.split('/')[1:])
        if member.name:
            archive.extract(member, root, filter='data')
(root / '.extracted').touch()
PY
fi
bash "$VINS_DESKTOP_DIR/scripts/build_ros2_native.sh"
bash "$VINS_DESKTOP_DIR/scripts/build_ros2.sh"
bash "$VINS_DESKTOP_DIR/scripts/convert_euroc_ros2.sh"
