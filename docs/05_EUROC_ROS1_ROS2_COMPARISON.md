# 原生 Ubuntu 22.04 EuRoC 复现实测

本页只记录当前物理主机实测。WSL 原报告保存在历史 tag；历史归档及冻结哈希保持原样

主机：Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，16 逻辑 CPU、约 30 GiB 内存

输入为相同 SHA256 的 MH_01_easy；OpenCV 4.2.0、Ceres 1.14.0、标定及算法参数保持原版。evo 使用 IMU/body 真值、SE(3) 对齐、不校正尺度，相邻位姿 RPE 约 0.1 秒间隔

DDR 流量不可用；CPU 能量节点默认不可读。GPU hwmon 功率不代表 CPU VIO 功耗

本分支保留 master 的 ROS 1 四轮原生复现结果；桌面 ROS 2 和板端 ROS 2 结果分别记录在 ros2-humble、codex/rk3588-ros2 的同名报告。本分支后续续写 RK3588 ROS 1 实测，当前 SDK 已锁定、下载待完成，尚无板端 ROS 1 结果。历史桌面清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

<!-- native-phase:ros1 -->
## ROS 1 原版参照与资源对照（2026-10-13）

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_MH01_baseline_r01 | stereo_imu_vio / ROS 1 standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.17 / 6.00 | -6 |
| native_MH01_baseline_r02 | stereo_imu_vio / ROS 1 standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.16 / 6.00 | -6 |
| native_MH01_metrics_r01 | stereo_imu_vio / ROS 1 standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.18 / 6.00 | -6 |
| native_MH01_metrics_r02 | stereo_imu_vio / ROS 1 standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.17 / 6.00 | -6 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_MH01_baseline_r01 | 163.33 | 未采样 | 仅 VINS | 77.94 / 69.05 | 未采样 |
| native_MH01_baseline_r02 | 163.50 | 未采样 | 仅 VINS | 79.05 / 67.24 | 未采样 |
| native_MH01_metrics_r01 | 163.91 | 未采样 | 仅 VINS | 77.29 / 68.37 | 未采样 |
| native_MH01_metrics_r02 | 163.31 | 未采样 | 仅 VINS | 75.56 / 67.39 | 未采样 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1/)

四轮使用相同 VINS 二进制，ATE/RPE 与轨迹逐轮一致；每轮初始化一次，无重置或双目配对丢弃，轨迹覆盖最后图像。CPU 范围为 163.31–163.91 秒，仅为本机这四轮的观察，不把不同 CPU 主机之间的变化归因于 Ubuntu/WSL

ROS 1 输入为 3682 对图像、36820 条 IMU；计数由 bag 核验，未向原节点添加消费端回调计数。清理退出均为 −6，复现了原版未 join 同步线程的 abort，功能完整性通过与退出缺陷分别记录；不能称为干净退出或稳定性全面通过

首次后台子进程中断及第二轮启动前的端口检查失败均已保留在[失败证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1_startup_failures/)。端口检查修复不改二进制、算法或参数；四个成功轮次独立验收，失败不计入性能统计

本阶段新 annotated tag 为 `baseline-ros1-native-ubuntu22-v1`，提交直接位于 `master`；历史 `baseline-ros1-euroc-v1` 不移动

补跑日志审计：phase03 复用了原控制台日志路径，使 phase02 的第二轮启动 stderr 被覆盖；旧归档中的该日志为空，保留原冻结清单，不伪装成完整 stderr。失败事件仍在，当时读取到的 traceback 按聊天工具输出补充为[注明来源的摘录](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1_startup_failure_audit/)。四个成功轮次的轨迹、采样、验收和哈希不受影响

正式阶段执行器现将控制台日志放入每个唯一阶段目录的 trials 子目录，补跑不再复用前次日志。该修正只改变日志路径，不改回放、算法或二进制

## RK3588 ROS 1 主机交叉构建（2026-10-14）

独立 codex/rk3588-ros1 从 master 8c7c8d2 继续，核心/config 不变。锁定 Focal/Noetic SDK、GCC 9.4，保持 OpenCV 4.2.0 / Ceres 1.14.0 / Eigen 3.3.9；视觉库构建和消费端链接通过，Ceres SuiteSparse/CXSparse/LAPACK/OpenMP 保留。SDK 绝对符号链接、Python 及原生库/头文件 CMake 导出重定位分别记录，失败保留

ros1-build02 五包构建、六个可执行文件和 70 个 ARM ELF 依赖闭包通过，未混用 SDK cv_bridge/OpenCV；cv_bridge 1.16.2 仅构建 VIO 所需 C++ 库，下载 C++ 源码不变，不提供 Python cv_bridge 扩展。编译路径和 core/config 核验通过，原 GeographicLib 嵌套输出已纳入闭包。此处尚无板端 ABI/节点或 VIO、CPU/ATE/RPE 结果，不能将主机退出 0 当作板端成功；[构建证据及 SHA256](../infra/rk3588/reference/ros1_cross_build_20261014/)

## RK3588 ROS 1 视觉库实际计算（2026-10-14）

ros1-legacy-smoke01 在实际 RK3588 Ubuntu 22.04 上通过原版本 OpenCV 4.2.0/Ceres 1.14.0。25 个非 glibc ARM 库文件 SHA256 和 ldd 无缺库，保留板端 glibc/loader；64×64 mono8 / stride 80 的 GFTT 八角点与 LK 位移误差小于 0.1 像素，输入未写；SuiteSparse/CXSparse 两后端均求得 x=10。ROS 2 共享回放结束并完成无残留审计后串行执行，无并行板端 VIO

这是独立 Focal/Noetic 视觉库的 ABI/计算探针，没有 ROS 1 节点或完整 VIO/性能结论；[实际板端原日志、动态库与 SHA256](../infra/rk3588/reference/ros1_legacy_board_20261014/)

## RK3588 Noetic 私有运行环境（2026-10-14）

ros1-runtime02 板端 4210 文件 SHA256、Python 3.8.10/NumPy 1.17.4/rosbag 导入、rosversion/roslaunch 1.17.4、VINS 动态库与双目/IMU 订阅就绪通过。实际 maps 为私有 OpenCV 4.2/Ceres/Python 和系统 libc，保留 Ubuntu 22.04 glibc/loader/系统 Python 3.10。结束审计无旧作业活进程

ROS master 退出 0，原 ROS 1 未 join 同步线程的清理 abort 为 −6，与桌面原版一致，如实记录，不称正常 VINS 退出。本阶段无 bag 输入或完整 VIO/轨迹/性能结论；首次包遗漏 SDK usr/bin/rosversion 的启动失败已归档，新独立候选补齐原脚本，依赖/算法/标定不变。[板端原日志、实际 maps、事件和逐文件 SHA256](../infra/rk3588/reference/ros1_runtime_20261014/)
