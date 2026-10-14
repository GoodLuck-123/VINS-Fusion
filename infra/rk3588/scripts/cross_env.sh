#!/usr/bin/env bash
# Source in a fresh host shell for both configure and build, not on the board.
if [[ -z "${BASH_VERSION:-}" ]]; then
  echo 'Enter bash before sourcing the cross environment' >&2
  return 1
fi
vins_cross_repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
export VINS_CROSS_ROOT="$vins_cross_repo/dependencies/toolchain/root"
export VINS_ARM_SYSROOT="$vins_cross_repo/dependencies/sysroots/ros2-humble/root"
export VINS_ARM_PREFIX="${VINS_ARM_PREFIX:-$(dirname "$vins_cross_repo")/.infra/rk3588/legacy}"
for vins_cross_path in "$VINS_CROSS_ROOT" "$VINS_ARM_SYSROOT"; do
  if [[ ! -f "$vins_cross_path/.vins-lock-sha256" ]]; then
    echo 'Run python3 infra/dependencies/fetch.py first' >&2
    return 1
  fi
done
export LD_LIBRARY_PATH="$VINS_CROSS_ROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_SYSROOT_DIR="$VINS_ARM_SYSROOT"
export PKG_CONFIG_LIBDIR="$VINS_ARM_SYSROOT/usr/lib/aarch64-linux-gnu/pkgconfig:$VINS_ARM_SYSROOT/usr/share/pkgconfig"
export PKG_CONFIG_PATH="$VINS_ARM_PREFIX/lib/pkgconfig:$VINS_ARM_PREFIX/share/pkgconfig"
unset vins_cross_repo vins_cross_path
