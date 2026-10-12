# VINS-Fusion / ROS 2 Humble

面向 RK3588 部署的个人 fork，保持 VINS 算法和 EuRoC 标定，以隔离环境完成迁移与性能对照。实验室目标是灰度单目相机 + 200 Hz IMU，双目用于参照与初始化验证；当前实测均为桌面 EuRoC 开环 VIO

**新机器或新 agent 从 [00 接手与迁移](docs/00_HANDOFF.md) 开始**，按环境重建、单目原生回放、真值评估的顺序确认，再开展板端工作

## 当前版本

`master` 保留 ROS 1 Noetic 参照；`ros2-humble` 包含 ROS 2 迁移、组件化、图像 owner 与 ROS Image / memfd / VGEM 三种可选传输，后者由运行参数选择。默认普通 ROS Image + share 图像入口，OpenCV 4.2.0 / Ceres 1.14.0 保持不变

单目/双目完整 EuRoC 输入、轨迹和进程退出已验证，三种传输各五次、两种模式共 30 次串行实验已归档。双目 memfd 在本机的配对 CPU 变化中位数为 −11.99%，单目 CPU 收益未确定；共享路径源端 PSS 明显降低，VGEM CPU 更高且双目背压减速。性能结论限本机 WSL/x86，数据和统计边界见 [05 对比实验](docs/05_EUROC_ROS1_ROS2_COMPARISON.md#shared-repeats)

板端依赖、实际相机、RGA、NEON、NPU、DDR 和功耗尚未验收；回环/GNSS/KITTI/RViz 也未做完整数据验收。下一步在新的 Ubuntu 主机和 RK3588 环境推进，当前 WSL 实验阶段结束

## 文档与源码导航

| 文档 | 用途 |
| --- | --- |
| [00 接手与迁移](docs/00_HANDOFF.md) | 当前状态、目录职责、新机起步和板端入口 |
| [01 RK3588 顶层任务书](docs/01_RK3588_DEPLOYMENT_PLAN.md) | 阶段、工作量与验收边界 |
| [02 Ubuntu 22.04 / ROS 1](docs/02_UBUNTU22_ROS1_SETUP.md) | 原版隔离环境重建 |
| [03 EuRoC / ROS 1 参照](docs/03_EUROC_ROS1_BASELINE.md) | 最初两轮运行与精度参照 |
| [04 Ubuntu 22.04 / ROS 2](docs/04_UBUNTU22_ROS2_SETUP.md) | 构建、回放、组件和传输参数 |
| [05 ROS 1 / ROS 2 对比实验](docs/05_EUROC_ROS1_ROS2_COMPARISON.md) | 历史与后续实验的统一报告 |
| [06 CPU 候选优化](docs/06_X86_CPU_EXPERIMENTS.md) | 尚未实施的候选项，供板端热点分析参考 |

`vins_estimator/` 是主 VIO 与 ROS 2 数据源/共享缓冲入口，`camera_models/` 是相机模型，`loop_fusion/` 和 `global_fusion/` 保留扩展模块，`config/` 保存传感器配置。构建、实验、评估、依赖锁和已提交证据在 `infra/desktop/`；新 agent 的工作约定见 [AGENTS.md](AGENTS.md)

克隆使用 `git clone --branch ros2-humble https://github.com/GoodLuck-123/VINS-Fusion.git`，进入仓库后按第 00、04 份文档重建。锁文件只支持 Linux x86_64；RK3588 必须另建 ARM 环境，不能直接运行 desktop bootstrap

## 上游与许可

源自 HKUST Aerial Robotics 的 [VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion)，作者、论文、引用及原版示例保存在 [上游历史说明](support_files/UPSTREAM_README.md)。源码遵循 [GPLv3](LICENCE)；上游 ROS 1 Docker 和硬件 launch 作为历史文件保留，当前 ROS 2 的可靠运行入口以第 04 份文档为准
