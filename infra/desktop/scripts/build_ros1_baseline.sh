#!/usr/bin/env bash
set -eo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
ROOT="$VINS_WORKSPACE_DIR"
source "$ROOT/scripts/ros1_env.sh"
set -u
JOBS="${VINS_BUILD_JOBS:-4}"
mkdir -p "$ROOT/.infra/src" "$ROOT/.infra/build" "$ROOT/.infra/legacy"
for archive in opencv-4.2.0 ceres-1.14.0 vision_opencv-1.16.2; do
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

cmake -S "$ROOT/.infra/src/opencv-4.2.0" -B "$ROOT/.infra/build/opencv" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/.infra/legacy" \
  -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_LIST=core,imgproc,imgcodecs,calib3d,features2d,flann,video,highgui \
  -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF -DBUILD_opencv_python2=OFF \
  -DBUILD_opencv_python3=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_FFMPEG=OFF \
  -DWITH_GSTREAMER=OFF -DWITH_V4L=OFF -DWITH_OPENCL=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF \
  -DWITH_EIGEN=OFF -DWITH_TIFF=OFF -DWITH_OPENEXR=OFF -DWITH_WEBP=OFF \
  -DWITH_JASPER=OFF -DWITH_PROTOBUF=OFF -DBUILD_JAVA=OFF
cmake --build "$ROOT/.infra/build/opencv" -j "$JOBS"
cmake --install "$ROOT/.infra/build/opencv"

cmake -S "$ROOT/.infra/src/ceres-1.14.0" -B "$ROOT/.infra/build/ceres" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/.infra/legacy" \
  -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF \
  -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF -DEigen3_DIR="$CONDA_PREFIX/share/eigen3/cmake" \
  -DEIGEN_INCLUDE_DIR="$CONDA_PREFIX/include/eigen3" -DCXX11=ON
cmake --build "$ROOT/.infra/build/ceres" -j "$JOBS"
cmake --install "$ROOT/.infra/build/ceres"

mkdir -p "$ROOT/.infra/bridge_ws/src" "$ROOT/.infra/vins_ws/src"
ln -sfn "$CONDA_PREFIX/share/catkin/cmake/toplevel.cmake" "$ROOT/.infra/bridge_ws/src/CMakeLists.txt"
ln -sfn "$ROOT/.infra/src/vision_opencv-1.16.2/cv_bridge" "$ROOT/.infra/bridge_ws/src/cv_bridge"
cmake -S "$ROOT/.infra/bridge_ws/src" -B "$ROOT/.infra/bridge_ws/build" \
  -DCMAKE_BUILD_TYPE=Release -DCATKIN_DEVEL_PREFIX="$ROOT/.infra/bridge_ws/devel" \
  -DPYTHON_EXECUTABLE="$CONDA_PREFIX/bin/python" -DOpenCV_DIR="$OpenCV_DIR" \
  -DCMAKE_PREFIX_PATH="$ROOT/.infra/legacy;$CONDA_PREFIX" -DCATKIN_ENABLE_TESTING=OFF
cmake --build "$ROOT/.infra/bridge_ws/build" -j "$JOBS"
set +u
source "$ROOT/.infra/bridge_ws/devel/setup.bash"
set -u

ln -sfn "$CONDA_PREFIX/share/catkin/cmake/toplevel.cmake" "$ROOT/.infra/vins_ws/src/CMakeLists.txt"
for package in camera_models vins_estimator loop_fusion global_fusion; do
  ln -sfn "$ROOT/VINS-Fusion/$package" "$ROOT/.infra/vins_ws/src/$package"
done
cmake -S "$ROOT/.infra/vins_ws/src" -B "$ROOT/.infra/vins_ws/build" \
  -DCMAKE_BUILD_TYPE=Release -DCATKIN_DEVEL_PREFIX="$ROOT/.infra/vins_ws/devel" \
  -DCMAKE_PROJECT_INCLUDE="$ROOT/scripts/native_cmake_overrides.cmake" \
  -DPYTHON_EXECUTABLE="$CONDA_PREFIX/bin/python" -DOpenCV_DIR="$OpenCV_DIR" -DCeres_DIR="$Ceres_DIR" \
  -DCMAKE_PREFIX_PATH="$ROOT/.infra/bridge_ws/devel;$ROOT/.infra/legacy;$CONDA_PREFIX" \
  -DEIGEN3_INCLUDE_DIR="$CONDA_PREFIX/include/eigen3" -DCATKIN_ENABLE_TESTING=OFF
cmake --build "$ROOT/.infra/vins_ws/build" -j "$JOBS"
