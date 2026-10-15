#!/usr/bin/env bash
# Source in a fresh shell. The target system's glibc/loader remain in use.
export VINS_INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VINS_BUILD_SOURCE_JSON="$VINS_INSTALL_ROOT/share/provenance/build_source.json"
export VINS_ROS_PREFIX="$VINS_INSTALL_ROOT/runtime/ros"
export LD_LIBRARY_PATH="$VINS_INSTALL_ROOT/app/lib:$VINS_INSTALL_ROOT/runtime/lib:$VINS_ROS_PREFIX/lib"
unset PYTHONHOME PYTHONPATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH ROS_PACKAGE_PATH ROS_ROOT ROS_ETC_DIR
export PYTHONNOUSERSITE=1
if test -d "$VINS_INSTALL_ROOT/runtime/python38"; then
    export PYTHONHOME="$VINS_INSTALL_ROOT/runtime/python38"
    export PYTHONPATH="$VINS_ROS_PREFIX/lib/python3/dist-packages:$VINS_INSTALL_ROOT/runtime/python"
    export PATH="$VINS_INSTALL_ROOT/bin:$PYTHONHOME/bin:$VINS_ROS_PREFIX/bin:/usr/bin:/bin"
    export CMAKE_PREFIX_PATH="$VINS_INSTALL_ROOT/app:$VINS_ROS_PREFIX"
    export ROS_PACKAGE_PATH="$VINS_ROS_PREFIX/share"
    export ROS_ROOT="$VINS_ROS_PREFIX/share/ros"
    export ROS_ETC_DIR="$VINS_ROS_PREFIX/etc/ros"
    export ROS_DISTRO=noetic ROS_VERSION=1 ROS_PYTHON_VERSION=3
    export ROS_IP="${ROS_IP:-127.0.0.1}"
else
    export PATH="$VINS_INSTALL_ROOT/bin:$VINS_ROS_PREFIX/bin:/usr/bin:/bin"
    export AMENT_PREFIX_PATH="$VINS_INSTALL_ROOT/app:$VINS_ROS_PREFIX"
    export PYTHONPATH="$VINS_INSTALL_ROOT/app/lib/python3.10/site-packages:$VINS_ROS_PREFIX/local/lib/python3.10/dist-packages:$VINS_ROS_PREFIX/lib/python3.10/site-packages:$VINS_INSTALL_ROOT/runtime/python"
    export RMW_IMPLEMENTATION="${VINS_RMW:-rmw_cyclonedds_cpp}"
    export ROS_DISTRO=humble ROS_VERSION=2 ROS_PYTHON_VERSION=3
    export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-121}" ROS_LOCALHOST_ONLY=1
    export CYCLONEDDS_URI="file://$VINS_INSTALL_ROOT/share/cyclonedds.xml"
    if test "$RMW_IMPLEMENTATION" = rmw_fastrtps_cpp; then
        export LD_LIBRARY_PATH="$VINS_INSTALL_ROOT/runtime/fastrtps/lib:$LD_LIBRARY_PATH"
        export AMENT_PREFIX_PATH="$VINS_INSTALL_ROOT/runtime/fastrtps:$AMENT_PREFIX_PATH"
    fi
fi
