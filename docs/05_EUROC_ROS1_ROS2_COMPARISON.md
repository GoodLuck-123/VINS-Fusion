# 原生 Ubuntu 22.04 EuRoC 复现实测

本页只记录当前物理主机实测。WSL 原报告保存在历史 tag；历史归档及冻结哈希保持原样

主机：Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，16 逻辑 CPU、约 30 GiB 内存

输入为相同 SHA256 的 MH_01_easy；OpenCV 4.2.0、Ceres 1.14.0、标定及算法参数保持原版。evo 使用 IMU/body 真值、SE(3) 对齐、不校正尺度，相邻位姿 RPE 约 0.1 秒间隔

DDR 流量不可用；CPU 能量节点默认不可读。GPU hwmon 功率不代表 CPU VIO 功耗

ROS 1 四轮及 ROS 2 两轮双目 copy 参照已完成，后续里程碑待执行。完整清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

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

<!-- native-phase:ros2_baseline -->
## ROS 2 当前版本的双目 copy 参照（2026-10-13）

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_ros2_baseline_stereo_standalone_copy_ros_01 | stereo_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.22 / 6.00 | 0 |
| native_ros2_baseline_stereo_standalone_copy_ros_02 | stereo_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 187.24 / 6.00 | 0 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_ros2_baseline_stereo_standalone_copy_ros_01 | 162.44 | 未采样 | 仅 VINS | 92.53 / 81.68 | 未采样 |
| native_ros2_baseline_stereo_standalone_copy_ros_02 | 159.78 | 未采样 | 仅 VINS | 95.07 / 81.36 | 未采样 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros2_baseline/)

两轮 ROS 2 都完整收到左右图各 3682 帧、36820 条 IMU，处理 3682 对图像，初始化一次，无重置/配对丢弃，末帧覆盖完整，VINS 与播放器都退出 0。1831 个位姿、1819 个真值匹配，ATE/RPE 与本机 ROS 1 四轮一致

与 ROS 1 两轮 metrics 参照的配置逐行对照，仅输出路径不同；仍是同一输入与标定、Fast DDS 独立 ROS 2 节点、原图像 copy 路径。ROS 1 VINS CPU 均值 163.61 秒，ROS 2 均值 161.11 秒；ROS 2 PSS 为 81.36–81.68 MiB，ROS 1 两轮 metrics 为 67.39–68.37 MiB。两轮、不同时间段且未固定频率/温控，CPU 接近，不据此认定稳定提速；各表仅采样 VINS，外部播放器未纳入

按用户要求在最新 ros2-humble `b250dc0` 的入口与参数上复现最小迁移里程碑行为；该实现已有组件/owner 框架，不能说它就是历史 `baseline-ros2-humble-v1` 的二进制。新 annotated tag 为 `baseline-ros2-native-ubuntu22-v1`，提交直接位于 ros2-humble

扩展入口冒烟通过：loop_fusion_node、global_fusion_node 启动存活并 SIGINT 退出 0，两个 KITTI 入口缺少参数时退出 1；VINS 启动/退出由两轮完整回放验证。源码和记录见本机 ROS 2 参照快照的 entrypoints_smoke 子目录，仅接口检查，不等于回环/GNSS/KITTI 数据验收

<!-- native-phase:components -->
## 组件与图像 owner：八轮单目/双目对照（2026-10-13）

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_components_stereo_standalone_copy_ros_01 | stereo_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 187.24 / 6.00 | 0 |
| native_components_stereo_standalone_share_ros_02 | stereo_imu_vio / standalone / ros/share | 1831 / 1819 | 0.252745 | 0.003083 | 187.23 / 6.00 | 0 |
| native_components_stereo_standalone_share_ros_03 | stereo_imu_vio / standalone / ros/share | 1831 / 1819 | 0.252745 | 0.003083 | 188.23 / 6.00 | 0 |
| native_components_stereo_standalone_copy_ros_04 | stereo_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.22 / 6.00 | 0 |
| native_components_mono_standalone_copy_ros_05 | mono_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.185564 | 0.002938 | 188.21 / 6.00 | 0 |
| native_components_mono_standalone_share_ros_06 | mono_imu_vio / standalone / ros/share | 1831 / 1819 | 0.185564 | 0.002938 | 188.21 / 6.01 | 0 |
| native_components_stereo_composed_copy_ros_07 | stereo_imu_vio / composed / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.88 / 6.00 | 0 |
| native_components_stereo_composed_share_ros_08 | stereo_imu_vio / composed / ros/share | 1831 / 1819 | 0.252745 | 0.003083 | 188.80 / 6.01 | 0 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_components_stereo_standalone_copy_ros_01 | 162.65 | 未采样 | 仅 VINS | 96.22 / 82.47 | 未采样 |
| native_components_stereo_standalone_share_ros_02 | 162.24 | 未采样 | 仅 VINS | 94.70 / 80.95 | 未采样 |
| native_components_stereo_standalone_share_ros_03 | 161.52 | 未采样 | 仅 VINS | 92.27 / 80.99 | 未采样 |
| native_components_stereo_standalone_copy_ros_04 | 159.07 | 未采样 | 仅 VINS | 96.75 / 83.09 | 未采样 |
| native_components_mono_standalone_copy_ros_05 | 109.67 | 未采样 | 仅 VINS | 88.37 / 74.61 | 未采样 |
| native_components_mono_standalone_share_ros_06 | 108.08 | 未采样 | 仅 VINS | 84.09 / 74.05 | 未采样 |
| native_components_stereo_composed_copy_ros_07 | 164.33 | 未采样 | 仅 VINS | 77.75 / 70.68 | 未采样 |
| native_components_stereo_composed_share_ros_08 | 165.48 | 未采样 | 仅 VINS | 77.08 / 69.97 | 未采样 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/components/)

八轮完整处理输入、末帧、初始化/重置及退出验收全部通过，各输出 1831 个位姿、1819 个真值匹配。同模式轨迹 CSV 的 SHA256 逐轮完全一致，单目 ATE/RPE 为 0.185564 / 0.002938 m，双目为 0.252745 / 0.003083 m；没有观察到 copy/share 精度变化

| 实验 | 共享图像数 | 入口物化次数 | 入口物化 (MiB) |
| --- | ---: | ---: | ---: |
| native_components_stereo_standalone_copy_ros_01 | 0 | 14728 | 5069.94 |
| native_components_stereo_standalone_share_ros_02 | 7364 | 0 | 0.00 |
| native_components_stereo_standalone_share_ros_03 | 7364 | 0 | 0.00 |
| native_components_stereo_standalone_copy_ros_04 | 0 | 14728 | 5069.94 |
| native_components_mono_standalone_copy_ros_05 | 0 | 7364 | 2534.97 |
| native_components_mono_standalone_share_ros_06 | 3682 | 0 | 0.00 |
| native_components_stereo_composed_copy_ros_07 | 0 | 14728 | 5069.94 |
| native_components_stereo_composed_share_ros_08 | 7364 | 0 | 0.00 |

share 消除了原生灰度入口的显式物化，copy 保留历史入口。两轮双目 standalone copy CPU 均值 160.86 秒，share 为 161.88 秒；单目单次 copy/share 为 109.67 / 108.08 秒；同进程 composed 为 164.33 / 165.48 秒。**入口减拷贝成立，当前少量重复不支持整机稳定提速结论**。同一部署/模式/RMW 内比较，composed 含数据源和容器，standalone 仅 VINS，不能跨范围直接算组件化加速比

composed 两轮各六组起始消息/像素地址核验通过，源端与订阅端一致，入口视图的共享或复制符合参数；全序列共享/物化计数另列上表。只读 owner、stride/回退、单目/双目前端十帧特征一致性与两种 RMW 组件生命周期探针已归档；局部 ASan 不覆盖全部依赖，不代表长期泄漏验收

本阶段提交直接位于 ros2-humble，新 annotated tag 为 `milestone-ros2-components-native-ubuntu22-v1`。VINS 组件二进制与前一阶段相同，未改算法、标定、依赖或默认线程参数
