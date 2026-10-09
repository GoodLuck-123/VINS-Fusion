#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
ROOT="$VINS_WORKSPACE_DIR"
mkdir -p "$ROOT/.infra/downloads" "$ROOT/data/euroc"
download() {
  local url="$1" destination="$2"
  if [[ -s "$destination" ]]; then return; fi
  curl --fail --location --retry 3 --connect-timeout 20 --output "$destination.part" "$url"
  mv "$destination.part" "$destination"
}
download https://codeload.github.com/opencv/opencv/tar.gz/refs/tags/4.2.0 "$ROOT/.infra/downloads/opencv-4.2.0.tar.gz"
download https://codeload.github.com/ceres-solver/ceres-solver/tar.gz/refs/tags/1.14.0 "$ROOT/.infra/downloads/ceres-1.14.0.tar.gz"
download https://codeload.github.com/ros-perception/vision_opencv/tar.gz/refs/tags/1.16.2 "$ROOT/.infra/downloads/vision_opencv-1.16.2.tar.gz"

# Original ETH endpoint first; the public mirror supplies the same ROS 1 bag.
BAG="$ROOT/data/euroc/MH_01_easy.bag"
if [[ ! -s "$BAG" ]]; then
  if ! curl --fail --location --connect-timeout 15 --max-time 30 --output "$BAG.part" \
    https://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.bag; then
    curl --fail --location --retry 3 --connect-timeout 20 --output "$BAG.part" \
      https://huggingface.co/datasets/kavehsgh/EuRoC_MAV_Dataset_Machine_Hall_Easy_01/resolve/main/MH_01_easy.bag
  fi
  mv "$BAG.part" "$BAG"
fi
printf '%s  %s\n' 57f440ccd68ec8dc8f9461269f5909656b86198bac3adfd677b1fcc7a1428fa9 "$BAG" | sha256sum --check
download https://raw.githubusercontent.com/rpng/open_vins/master/ov_data/euroc_mav/MH_01_easy.csv "$ROOT/data/euroc/MH_01_easy_groundtruth.csv"
sha256sum "$ROOT/.infra/downloads/"*.tar.gz "$BAG" > "$ROOT/.infra/downloads/SHA256SUMS"
sha256sum "$ROOT/data/euroc/MH_01_easy_groundtruth.csv" >> "$ROOT/.infra/downloads/SHA256SUMS"
