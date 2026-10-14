# ROS 1 ARM SDK 依赖解析

独立分支 codex/rk3588-ros1 从 master 最新 8c7c8d2 建立，原 ROS 2 工作区与板端运行包保持固定。主机私有 APT 空状态解析 Focal/Noetic final：807 个 ARM/all SDK 包、36 个 amd64/all GCC 9.4 交叉工具链包，只下载索引，尚未下载库、构建或运行板端 ROS 1

Noetic final 使用 ROS 官方 Dockerfile 的独立 snapshot 公钥指纹 4B63CF8FDE49746E98FA01DDAD19BAB3CBF125EA，InRelease 验签及 ARM Packages SHA256 通过；Ubuntu 索引由系统 Ubuntu 公钥验签。所有下载锁取自已认证 Packages 的 SHA256，不使用 print-uris 的 MD5 作为验收哈希

Noetic 官方平台为 Focal / Python 3.8 / Boost 1.71，独立前缀保留这些 ABI，板端继续 Ubuntu 22.04，实际运行兼容性待探针验收。OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9 仍从固定源码重建；与 ROS 2 的工具链/传递依赖差异需单列，不将性能差异仅归因于 ROS 版本

官方平台：https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0003.rst
官方 snapshot 配置：https://raw.githubusercontent.com/osrf/docker_images/master/ros/noetic/ubuntu/focal/ros-core/Dockerfile
