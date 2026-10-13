# 原生 Ubuntu 22.04 / ROS 1 参照环境

更新日期：2026-10-13

本页针对当前物理 Ubuntu 22.04.5 x86_64 主机；四轮 MH_01_easy 双目 IMU 复现已完成，实测见 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)。先读 [交接入口](00_HANDOFF.md)和[复现清单](07_NATIVE_UBUNTU_REPRODUCTION.md)

## 固定环境

ROS Noetic 使用工程内 RoboStack 包，不向 Ubuntu 系统加入其他版本 apt 源。保持 OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、GCC 13.4.0；cv_bridge 1.16.2 按相同 OpenCV 源码重建，不能混用系统 OpenCV 或预编译 cv_bridge

原生包按 `infra/desktop/ros1-linux-64.lock` 创建，视觉/求解器源码和数据按 SHA256 校验，Python 评估按 `infra/desktop/uv.lock` 管理。原生锁只支持 Linux x86_64，不在 ARM 上使用

命令从 Git 仓库根目录执行，父目录为运行工作区：

| 路径 | 用途 |
| --- | --- |
| `../.infra/ros1` | ROS 1 与隔离编译器、数值库 |
| `../.infra/legacy` | OpenCV 4.2.0 / Ceres 1.14.0 |
| `../.infra/bridge_ws`、`vins_ws` | cv_bridge / VINS 构建与安装 |
| `infra/desktop/.venv` | uv 评估，独立于 ROS Python |
| `../data/euroc` | MH_01_easy bag、IMU/body 真值 |
| `../results/ros1` | 每轮配置、轨迹、完整日志、采样和评估 |

不在仓库根目录建软链接，不复制旧机器安装前缀作为新机环境

## 构建与隔离核验

本机已用以下入口从零安装和构建成功。先确认 checkout 为 master，且原算法工作树无未处理修改：

```bash
git status --short --branch
git switch master
VINS_BUILD_JOBS=4 bash infra/desktop/scripts/bootstrap_baseline.sh
```

已有依赖时仅重建：

```bash
VINS_BUILD_JOBS=4 bash infra/desktop/scripts/build_ros1_baseline.sh
```

在新 ROS shell 中 source 并检查实际动态库路径：

```bash
source infra/desktop/scripts/ros1_env.sh
python infra/desktop/scripts/verify_native_environment.py
```

四个 package、cv_bridge 已构建通过；ldd/CMakeCache 核验通过，视觉库和 Ceres 均来自 ROS 1 专用前缀。构建兼容修补位于 infra，不修改 VINS 原算法。切换源码后必须重建，已有安装不代表当前源码；不要 source 系统 `/opt/ros` 或在 ROS shell 激活 uv venv

## 数据与回放

数据源为固定 SHA256 的 EuRoC MH_01_easy，752×480 mono8、双目 20 Hz、IMU 200 Hz。真值为原锁定的 IMU/body 状态 CSV，不使用变换到左相机的真值

本轮四次完整回放的正式入口：

```bash
bash infra/desktop/scripts/run_native_ros1_reproduction.sh
```

它使用独立 ROS master，等待订阅就绪，启用 use_sim_time，完整回放后排空，再在独立 uv shell 评估和验收。只改实验配置中的绝对输出路径，保留标定与算法参数。结果目录拒绝覆盖；本机四个默认名字已使用，补跑或新实验必须给新的显式名字：

```bash
bash infra/desktop/scripts/run_native_ros1_reproduction.sh new_run_01 new_run_02
```

单轮可在 ROS shell 使用 `run_euroc_baseline.py --name 新名称 --rate 1`，在普通 shell 使用：

```bash
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python   infra/desktop/scripts/evaluate_baseline.py ../results/ros1/新名称
```

## 后台与结果

大批次使用用户级临时 systemd 服务，避免工具 shell 结束后后台子进程消失；不安装持久服务或 timer。正式执行器是 `run_local_phase.py`，接收输出目录、命令与可选 JSON argv completion hook，终止事件与通知退出码分别记录。hook 留在本机 `.local-tests/`，不迁移旧聊天 ID

本轮 `vins-native-ros1-phase03.service` 已完成，原始阶段记录在 `../results/ubuntu22-reproduction/`。每轮 VINS/rosbag PID 不同，评估和间隔阶段没有 VINS 进程；查看阶段 state.json 或服务状态更可靠

所有成功轮次都有 1831 个位姿、1819 个真值匹配、末帧覆盖完整。功能完整性通过；原版未 join 同步线程的清理 abort 仍记录为 −6，不改成零。CPU 是 VINS 全线程累计值，约 1 秒采样 RSS/PSS 是各进程峰值，不是 DDR 流量或功耗；本轮未采样外部播放器资源

[统一报告](05_EUROC_ROS1_ROS2_COMPARISON.md)列出回放/排空、精度、CPU/RSS/PSS及失败证据；[本机快照](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1/)附 SHA256。历史 WSL 数据不再作为本页实测，保留在原 tag 与冻结归档中
