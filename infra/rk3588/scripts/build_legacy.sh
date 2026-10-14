#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
build="${VINS_ARM_BUILD:-$(dirname "$repo")/.infra/rk3588/build-legacy-sysroot}"
jobs="${VINS_BUILD_JOBS:-4}"
toolchain="$repo/infra/rk3588/cmake/aarch64.cmake"
mkdir -p "$build" "$VINS_ARM_PREFIX"
opencv_source="$build/opencv-source"
opencv_patch="$repo/infra/rk3588/patches/opencv-4.2.0-gcc11.patch"
patch_sha=$(sha256sum "$opencv_patch" | cut -d' ' -f1)
if [[ ! -d "$opencv_source" ]]; then
  cp -a "$repo/dependencies/sources/opencv/4.2.0" "$opencv_source"
  patch --batch -d "$opencv_source" -p1 < "$opencv_patch"
  printf '%s\n' "$patch_sha" > "$opencv_source/.vins-build-patch-sha256"
fi
test "$(cat "$opencv_source/.vins-build-patch-sha256")" = "$patch_sha" || {
  echo 'Incomplete or changed OpenCV patch; preserve this build and select a new VINS_ARM_BUILD' >&2
  exit 1
}
common=(-G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_INSTALL_PREFIX="$VINS_ARM_PREFIX" -DCMAKE_INSTALL_LIBDIR=lib)

cmake -S "$repo/dependencies/sources/eigen/3.3.9" -B "$build/eigen" "${common[@]}" \
  -DBUILD_TESTING=OFF -DEIGEN_BUILD_DOC=OFF
cmake --install "$build/eigen"

cmake -S "$opencv_source" -B "$build/opencv" "${common[@]}" \
  -DBUILD_LIST=core,imgproc,imgcodecs,calib3d,features2d,flann,video,highgui \
  -DWITH_ADE=OFF -DBUILD_opencv_gapi=OFF -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF \
  -DBUILD_EXAMPLES=OFF -DBUILD_opencv_python2=OFF -DBUILD_opencv_python3=OFF \
  -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF \
  -DWITH_V4L=OFF -DWITH_OPENCL=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF -DWITH_EIGEN=OFF \
  -DWITH_TIFF=OFF -DWITH_OPENEXR=OFF -DWITH_WEBP=OFF -DWITH_JASPER=OFF \
  -DWITH_PROTOBUF=OFF -DBUILD_JAVA=OFF
cmake --build "$build/opencv" -j "$jobs"
cmake --install "$build/opencv"

cmake -S "$repo/dependencies/sources/ceres/1.14.0" -B "$build/ceres" "${common[@]}" \
  -DCMAKE_PREFIX_PATH="$VINS_ARM_PREFIX;$VINS_ARM_SYSROOT/usr" \
  -DCMAKE_LIBRARY_PATH="$VINS_ARM_SYSROOT/usr/lib/aarch64-linux-gnu/blas;$VINS_ARM_SYSROOT/usr/lib/aarch64-linux-gnu/lapack" \
  -DBLA_VENDOR=Generic -DCMAKE_DISABLE_FIND_PACKAGE_TBB=TRUE -DSUITESPARSE=ON -DLAPACK=ON \
  -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF \
  -DBUILD_BENCHMARKS=OFF -DEigen3_DIR="$VINS_ARM_PREFIX/share/eigen3/cmake" \
  -DEIGEN_INCLUDE_DIR="$VINS_ARM_PREFIX/include/eigen3" -DCXX11=ON
cmake --build "$build/ceres" -j "$jobs"
cmake --install "$build/ceres"
if grep -Eq '^#define CERES_NO_(LAPACK|SUITESPARSE|CXSPARSE)' \
  "$VINS_ARM_PREFIX/include/ceres/internal/config.h"; then
  echo 'Reference Ceres sparse/LAPACK features were disabled' >&2
  exit 1
fi
"$VINS_CROSS_ROOT/usr/bin/aarch64-linux-gnu-readelf" -h -d \
  "$VINS_ARM_PREFIX/lib/libopencv_core.so.4.2.0" "$VINS_ARM_PREFIX/lib/libceres.so.1.14.0"
printf 'ARM reference libraries installed: %s\n' "$VINS_ARM_PREFIX"
