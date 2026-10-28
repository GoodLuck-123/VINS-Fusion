# 第三方源码、驱动和 SDK

## Quick Start

无需手动 clone 依赖。执行 `./vins build --target board` 或 `./vins run`，构建器按 buildkit/sources.lock.json 的来源和 SHA256 补齐本目录，并在主机编译

## 当前内容

OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、vision_opencv 1.16.2 的可见源码放在 opencv/、ceres/、eigen/、vision_opencv/。下载内容 Git 忽略，归档在 cache/archives；重新 clone 后由相同命令补齐

v0.1 没有硬件驱动/SDK；v0.2 在此增加对应来源与锁，不借用板端现有工作区。集中补丁和兼容选项在 buildkit，构建时副本在 build，原始第三方下载内容不直接改写
