# 接手与当前状态

更新日期：2026-10-14

原生 Ubuntu 桌面复现已结束，本分支从 ROS 1 master 最新 8c7c8d2 建立，当前 checkout 为 codex/rk3588-ros1，继续 RK3588 主机交叉编译与离线板端任务。桌面 ROS 1 结果保留在 master，桌面 ROS 2 结果在 ros2-humble，板端 ROS 2 在 codex/rk3588-ros2；历史复现清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

ROS 1 锁定依赖已重新安装，OpenCV 4.2.0 / Ceres 1.14.0 / cv_bridge / 四个 package 已完成源码构建。四轮完整 EuRoC 回放、采样和评估已通过；同一二进制、各一次初始化、无重置/配对丢弃、末帧覆盖。新里程碑为 `baseline-ros1-native-ubuntu22-v1`，原版清理 abort 单列记录

本分支的详细环境入口是 [ROS 1 搭建说明](UBUNTU22_ROS1_BASELINE_SETUP.md)。本分支环境及实测页已替换为原生 Ubuntu 结果；统一实测在 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

命令从仓库根目录执行。ROS/C++ 前缀与 Python 评估环境分开；安装、数据和完整日志在父目录 `.infra/`、`data/`、`results/`，不要在根目录建软链接。每次切换源码先重建，再在新 shell source 对应环境

历史分支、tag、归档及 SHA256 保留。复现成功前不覆盖冻结数据、不写“完成”，失败现场保留；不重启历史桌面/神经网络批次；当前板端任务按用户授权逐项验收。本轮没有远端 push 授权

## RK3588 ROS 1 目标分支

当前板端工作位于 codex/rk3588-ros1，从 master 最新 8c7c8d2 新建独立工作区 /home/eric/projects/VINS-Fusion-rk3588-ros1。原 master、ROS 2 分支/tag 保留；ROS 2 组件批次的源码/运行包固定，本分支只准备主机侧 ROS 1 依赖，尚未构建或运行板端节点

Noetic final ARM 索引及 Ubuntu Focal 索引认证通过，807 个目标 SDK 包、36 个 GCC 9.4 工具链包已固定 SHA256；OpenCV 4.2.0 / Ceres 1.14.0 / Eigen 3.3.9 保留。一条命令下载和空目录约定见 [第 09 份文档](09_DEPENDENCIES.md)。实际 Ubuntu 22.04 板端 ABI/视觉库/节点和完整回放仍需验收；板端依旧离线，下载仅在本机进行

ros1-fetch01 已完成并离线重验四个源码/843 个锁定包，GCC 9.4 主机探针通过，依赖证据见第 09 份文档。下一阶段在独立 ../.infra/rk3588/ros1-legacy/ 构建固定版本视觉库，实际板端库/节点尚未验收；当前主机准备工作不影响 ROS 2 板端批次

## ROS 1 ARM 构建状态

ros1-fetch01 下载与离线哈希复核已通过，依赖里程碑 commit 30b9d96 / tag milestone-rk3588-ros1-dependencies-v1。首次视觉库构建 ros1-legacy01 在主机 CMake 启动时失败，原证据保留 infra/rk3588/reference/ros1_legacy01_failure/

Focal 工具链的旧主机 libstdc++ 抢占 Jammy CMake，现仅将编译器 isl/gmp/mpc/mpfr 与 ARM binutils 主机支持库暴露到 LD_LIBRARY_PATH，保留系统主机 libc/libstdc++。系统 CMake 3.22.1 与 GCC 9 生成 AArch64 对象均通过，ros1-legacy02 在主机后台重建。OpenCV 4.2/Ceres 1.14/Eigen 3.3.9、原 Carotene 参数和目标依赖均未改变；板端 ABI/ROS 1 回放仍待验收
