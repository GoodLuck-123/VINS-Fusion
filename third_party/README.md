# 第三方源码、驱动和 SDK

## Quick Start

开源依赖无需手动 clone；闭源 Spinnaker 3.1.0.79 ARM64 的三个归档先按 buildkit/spinnaker.lock.json 放入 cache/archives，构建时逐一校验后私有提取。执行 `./vins build --target board` 或 `./vins run`，构建器按 buildkit/sources.lock.json 的来源和 SHA256 补齐本目录，并在主机编译

## 当前内容

OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、vision_opencv 1.16.2 的可见源码放在 opencv/、ceres/、eigen/、vision_opencv/。下载内容 Git 忽略，归档在 cache/archives；重新 clone 后由相同命令补齐

v0.2 的 `drivers/` 是本工程最小相机/GNW适配源码，纳入 Git；`spinnaker/opt/spinnaker/` 是厂商 SDK 的可见提取位置，Git 忽略。运行包显式携带 GenTL 插件、私有 USB 运行依赖与许可证，不借用板端现有工作区。集中补丁和兼容选项在 buildkit，构建时副本在 build，原始第三方下载内容不直接改写
