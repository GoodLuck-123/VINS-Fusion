#!/usr/bin/env bash
set -eo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
ROOT="$VINS_WORKSPACE_DIR"
source "$VINS_DESKTOP_DIR/scripts/ros2_env.sh"
set -u
JOBS="${VINS_BUILD_JOBS:-4}"
mkdir -p "$ROOT/.infra/src" "$ROOT/.infra/build" "$ROOT/.infra/legacy_ros2"
for archive in opencv-4.2.0 ceres-1.14.0; do
  if [[ ! -f "$ROOT/.infra/src/$archive/.extracted" ]]; then
    mkdir -p "$ROOT/.infra/src/$archive"
    python - "$ROOT/.infra/downloads/$archive.tar.gz" "$ROOT/.infra/src/$archive" <<'PY'
import sys, tarfile
from pathlib import Path
with tarfile.open(sys.argv[1]) as archive:
    root = archive.getnames()[0].split('/')[0] + '/'
    for member in archive.getmembers():
        if not member.name.startswith(root): continue
        member.name = member.name[len(root):]
        if member.name: archive.extract(member, sys.argv[2], filter='data')
Path(sys.argv[2], '.extracted').touch()
PY
  fi
done

cmake -S "$ROOT/.infra/src/opencv-4.2.0" -B "$ROOT/.infra/build/ros2-opencv" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/.infra/legacy_ros2" \
  -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_LIST=core,imgproc,imgcodecs,calib3d,features2d,flann,video,highgui \
  -DWITH_ADE=OFF -DBUILD_opencv_gapi=OFF -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF -DBUILD_opencv_python2=OFF \
  -DBUILD_opencv_python3=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_FFMPEG=OFF \
  -DWITH_GSTREAMER=OFF -DWITH_V4L=OFF -DWITH_OPENCL=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF \
  -DWITH_EIGEN=OFF -DWITH_TIFF=OFF -DWITH_OPENEXR=OFF -DWITH_WEBP=OFF \
  -DWITH_JASPER=OFF -DWITH_PROTOBUF=OFF -DBUILD_JAVA=OFF
cmake --build "$ROOT/.infra/build/ros2-opencv" -j "$JOBS"
cmake --install "$ROOT/.infra/build/ros2-opencv"

cmake -S "$ROOT/.infra/src/ceres-1.14.0" -B "$ROOT/.infra/build/ros2-ceres" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/.infra/legacy_ros2" \
  -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF \
  -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF -DEigen3_DIR="$CONDA_PREFIX/share/eigen3/cmake" \
  -DEIGEN_INCLUDE_DIR="$CONDA_PREFIX/include/eigen3" -DCXX11=ON
cmake --build "$ROOT/.infra/build/ros2-ceres" -j "$JOBS"
cmake --install "$ROOT/.infra/build/ros2-ceres"
