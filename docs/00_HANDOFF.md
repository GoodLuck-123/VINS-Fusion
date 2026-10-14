# 接手与当前状态

更新日期：2026-10-13

当前任务是在物理 Ubuntu 22.04 主机复现 WSL 已完成的全部桌面实验，按里程碑更新文档并分别提交。先读 [复现清单](07_NATIVE_UBUNTU_REPRODUCTION.md)；当前 checkout 为 `master`，ROS 1 结果直接提交在此；后续 ROS 2 直接使用 `ros2-humble` 最新提交，不另建复现分支

ROS 1 锁定依赖已重新安装，OpenCV 4.2.0 / Ceres 1.14.0 / cv_bridge / 四个 package 已完成源码构建。四轮完整 EuRoC 回放、采样和评估已通过；同一二进制、各一次初始化、无重置/配对丢弃、末帧覆盖。新里程碑为 `baseline-ros1-native-ubuntu22-v1`，原版清理 abort 单列记录

本分支的详细环境入口是 [ROS 1 搭建说明](UBUNTU22_ROS1_BASELINE_SETUP.md)。本分支环境及实测页已替换为原生 Ubuntu 结果；统一实测在 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

命令从仓库根目录执行。ROS/C++ 前缀与 Python 评估环境分开；安装、数据和完整日志在父目录 `.infra/`、`data/`、`results/`，不要在根目录建软链接。每次切换源码先重建，再在新 shell source 对应环境

历史分支、tag、归档及 SHA256 保留。复现成功前不覆盖冻结数据、不写“完成”，失败现场保留；无需重启神经网络或板端实验。本轮没有远端 push 授权

## 2026-10-14 用户授权推送

本机 ROS 1 桌面结果仍在 master 独立提交；后续板端代码在从 master 8c7c8d2 建立的 codex/rk3588-ros1，不合并 ROS 2 核心。用户现授权核验后推送 master、ros2-humble 和两个 RK3588 目标分支及所属新增 tag，仅 fast-forward/新增 refs，历史 tag 保留

代码/文档全部由主机维护，板端没有 Git 仓库，有效运行包哈希与主机一致；29 个旧作业的 441 份日志均有已回收主机副本，无板端独有待提交源码/文档。待推内容不含下载依赖、构建库、bag、私钥或 GitHub token；发布前证据在 codex/rk3588-ros2 的 infra/rk3588/reference/publication_check_20261014/，冻结“未 push”状态不改写
