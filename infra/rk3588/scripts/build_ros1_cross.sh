#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
workspace="${VINS_ROS1_WORKSPACE:-$(dirname "$repo")/.infra/rk3588/ros1_ws}"
export VINS_ARM_ROS_PREFIX="$workspace/devel"
ros="$VINS_ARM_SYSROOT/opt/ros/noetic"
# Host Python runs pure catkin/empy helpers only, never target extension modules.
export PYTHONPATH="$ros/lib/python3/dist-packages:$VINS_ARM_SYSROOT/usr/lib/python3/dist-packages"
export ROS_PYTHON_VERSION=3
mkdir -p "$workspace/build" "$VINS_ARM_ROS_PREFIX"
# VIO uses only the cv_bridge C++ library. Keep the downloaded source pristine;
# disable the optional Boost/Python extension in a dedicated build source copy.
bridge="$workspace/cv_bridge_source"
python3 - "$repo/dependencies/sources/cv_bridge_ros1/1.16.2/cv_bridge" "$bridge" <<'PATCH'
import pathlib,shutil,sys
source,dest=map(pathlib.Path,sys.argv[1:])
if dest.exists(): shutil.rmtree(dest)
shutil.copytree(source,dest)
for relative in ['CMakeLists.txt','src/CMakeLists.txt']:
    path=dest/relative
    text=path.read_text().replace('if(NOT ANDROID)', 'if(NOT ANDROID AND VINS_CV_BRIDGE_PYTHON)')
    text=text.replace('catkin_python_setup()', 'if(VINS_CV_BRIDGE_PYTHON)\ncatkin_python_setup()\nendif()')
    path.write_text(text)
PATCH
common=(-G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$repo/infra/rk3588/cmake/aarch64.cmake"
  -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=OFF
  -DCATKIN_DEVEL_PREFIX="$VINS_ARM_ROS_PREFIX" -DCMAKE_INSTALL_PREFIX="$workspace/install"
  -DCMAKE_PREFIX_PATH="$VINS_ARM_ROS_PREFIX;$VINS_ARM_PREFIX;$ros;$VINS_ARM_SYSROOT/usr"
  -DPYTHON_EXECUTABLE=/usr/bin/python3
  -DOpenCV_DIR="$VINS_ARM_PREFIX/lib/cmake/opencv4"
  -DCeres_DIR="$VINS_ARM_PREFIX/lib/cmake/Ceres"
  -Dcv_bridge_DIR="$VINS_ARM_ROS_PREFIX/share/cv_bridge/cmake"
  -Dcamera_models_DIR="$VINS_ARM_ROS_PREFIX/share/camera_models/cmake"
  -DEigen3_DIR="$VINS_ARM_PREFIX/share/eigen3/cmake"
  -DEIGEN3_INCLUDE_DIR="$VINS_ARM_PREFIX/include/eigen3"
  -DCMAKE_DISABLE_FIND_PACKAGE_TBB=TRUE -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
  -DCMAKE_PROJECT_INCLUDE="$repo/infra/desktop/scripts/native_cmake_overrides.cmake")
for package in cv_bridge camera_models vins_estimator loop_fusion global_fusion; do
  source="$repo/$package"
  if [[ "$package" = cv_bridge ]]; then source="$bridge"; fi
  cmake -S "$source" -B "$workspace/build/$package" "${common[@]}" -DVINS_CV_BRIDGE_PYTHON=OFF
  cmake --build "$workspace/build/$package" -j "${VINS_BUILD_JOBS:-4}"
done
"$VINS_CROSS_ROOT/usr/bin/aarch64-linux-gnu-readelf" -h -d "$VINS_ARM_ROS_PREFIX/lib/vins/vins_node"
printf 'ARM ROS 1 build complete; board ABI and VIO validation still required: %s\n' "$VINS_ARM_ROS_PREFIX"
