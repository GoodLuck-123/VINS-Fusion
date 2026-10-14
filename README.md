# VINS-Fusion / ROS 2 Humble

面向 RK3588 部署的个人 fork，保持 VINS 算法和 EuRoC 标定，以隔离环境完成迁移与性能对照。实验室目标是灰度单目相机 + 200 Hz IMU，双目用于参照与初始化验证；当前已完成桌面 EuRoC 开环 VIO 及 RK3588 首轮完整双目基线

**新机器或新 agent 从 [00 接手与迁移](docs/00_HANDOFF.md) 开始**，按环境重建、单目原生回放、真值评估的顺序确认，再开展板端工作

## 当前版本

`master` 保留 ROS 1 Noetic 参照；`ros2-humble` 包含 ROS 2 迁移、组件化、图像 owner 与 ROS Image / memfd / VGEM 三种可选传输，后者由运行参数选择。默认普通 ROS Image + share 图像入口，OpenCV 4.2.0 / Ceres 1.14.0 保持不变

物理 Ubuntu 22.04.5 / Ryzen 7 9800X3D 主机已完成全部桌面里程碑与交接核验。ROS 1 四轮已完成并直接提交到 master；ROS 2 在现有 ros2-humble 上完成锁定依赖重建及两轮完整双目 copy 验收。组件/owner 八轮已验收，同模式轨迹完全一致，入口减拷贝成立但未证明稳定整机提速；两轮 PMU 及四轮共享传输已验收，摘要与轨迹一致、memfd 槽位全部归还；VGEM 两轮及 30 次重复均已验收，52 轮完整复现结束。五次重复未显示 memfd 合计 CPU 收益，VGEM 消费端 CPU 明显增加，共享路径源端 PSS 较低，不沿用旧 WSL 性能数值作为本机结论。实际结果见 [05 本机实测](docs/05_EUROC_ROS1_ROS2_COMPARISON.md)，进度见 [07 复现清单](docs/07_NATIVE_UBUNTU_REPRODUCTION.md)

板端依赖、首轮双目基线及单目/组件/owner 对照已验收，PMU 完整对照与 memfd/DMA heap 计算探针已通过，ROS Image/memfd 完整共享对照已通过，DMA heap 完整 VIO 已通过，ROS 1 运行环境和唯一双目回放/评估已通过，合计 15 个去重配置各一次，原 ROS 1 清理 abort 如实单列；实际相机、RGA、自研 NEON、NPU、DDR 带宽和功耗尚未验收，回环/GNSS/KITTI/RViz 也未做完整数据验收。原生 Ubuntu 复现已完成，历史 WSL tag 与冻结归档保持原样

## 文档与源码导航

| 文档 | 用途 |
| --- | --- |
| [00 接手与迁移](docs/00_HANDOFF.md) | 当前状态、目录职责、新机起步和板端入口 |
| [01 RK3588 顶层任务书](docs/01_RK3588_DEPLOYMENT_PLAN.md) | 阶段、工作量与验收边界 |
| [02 Ubuntu 22.04 / ROS 1](docs/02_UBUNTU22_ROS1_SETUP.md) | 原版隔离环境重建 |
| [03 EuRoC / ROS 1 参照](docs/03_EUROC_ROS1_BASELINE.md) | 本机四轮运行与精度参照 |
| [04 Ubuntu 22.04 / ROS 2](docs/04_UBUNTU22_ROS2_SETUP.md) | 构建、回放、组件和传输参数 |
| [05 ROS 1 / ROS 2 对比实验](docs/05_EUROC_ROS1_ROS2_COMPARISON.md) | 当前物理主机实测，旧报告保存在 tag |
| [06 CPU 候选优化](docs/06_X86_CPU_EXPERIMENTS.md) | 尚未实施的候选项，供板端热点分析参考 |
| [07 原生 Ubuntu 复现](docs/07_NATIVE_UBUNTU_REPRODUCTION.md) | 里程碑顺序、状态及失败处理 |
| [08 RK3588 工作流](docs/08_RK3588_WORKFLOW.md) | 免密 SSH、scp/远端作业、交叉编译及板端验收 |
| [09 依赖下载](docs/09_DEPENDENCIES.md) | clone 后一个命令下载固定版本源码、交叉工具链与 ARM ROS 2 SDK |
| [10 阶段事件核对](docs/10_PHASE_EVENT_AUDIT.md) | 积压通知去重、有效产物和失败阶段统一结论 |

`vins_estimator/` 是主 VIO 与 ROS 2 数据源/共享缓冲入口，`camera_models/` 是相机模型，`loop_fusion/` 和 `global_fusion/` 保留扩展模块，`config/` 保存传感器配置。构建、实验、评估、依赖锁和已提交证据在 `infra/desktop/`；新 agent 的工作约定见 [AGENTS.md](AGENTS.md)

克隆使用 `git clone --branch ros2-humble https://github.com/GoodLuck-123/VINS-Fusion.git`，进入仓库后按第 00、04 份文档重建。锁文件只支持 Linux x86_64；RK3588 必须另建 ARM 环境，不能直接运行 desktop bootstrap

## 上游与许可

源自 HKUST Aerial Robotics 的 [VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion)，作者、论文、引用及原版示例保存在 [上游历史说明](support_files/UPSTREAM_README.md)。源码遵循 [GPLv3](LICENCE)；上游 ROS 1 Docker 和硬件 launch 作为历史文件保留，当前 ROS 2 的可靠运行入口以第 04 份文档为准

RK3588 板端工作位于 codex/rk3588-ros2，免密 SSH 与 C++ scp/运行/日志回收工具已验证；ARM 视觉库、统一依赖下载、perf、ROS 2 构建及板端生命周期通过，首轮完整双目 VIO 输入/末帧/退出与 ATE/RPE 已验收。下载在联网主机完成，优先本机交叉编译，各配置仅一轮，具体见第 08 份文档

板端依赖统一执行 `python3 infra/dependencies/fetch.py` 下载，Git 只保留锁和空目录占位；OpenCV/Ceres/Eigen/cv_bridge、交叉工具链及 ARM Humble 包按 SHA256 校验，详见第 09 份说明
