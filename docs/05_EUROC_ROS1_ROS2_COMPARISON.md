# 原生 Ubuntu 22.04 EuRoC 复现实测

本页只记录当前物理主机实测。WSL 原报告保存在历史 tag；历史归档及冻结哈希保持原样

主机：Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，16 逻辑 CPU、约 30 GiB 内存

输入为相同 SHA256 的 MH_01_easy；OpenCV 4.2.0、Ceres 1.14.0、标定及算法参数保持原版。evo 使用 IMU/body 真值、SE(3) 对齐、不校正尺度，相邻位姿 RPE 约 0.1 秒间隔

DDR 流量不可用；CPU 能量节点默认不可读。GPU hwmon 功率不代表 CPU VIO 功耗

ROS 1 四轮、ROS 2 两轮参照、八轮组件/owner、两轮 PMU、四轮共享传输及两轮 VGEM 已完成，累计 52 轮；完整回放复现及最终交接核验已结束。完整清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

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

<!-- native-phase:pmu -->
## 用户态 CPU PMU 对照

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_pmu_stereo_standalone_copy_ros_01 | stereo_imu_vio / standalone / ros/copy | 1831 / 1819 | 0.252745 | 0.003083 | 188.22 / 6.00 | 0 |
| native_pmu_stereo_standalone_share_ros_02 | stereo_imu_vio / standalone / ros/share | 1831 / 1819 | 0.252745 | 0.003083 | 187.23 / 6.01 | 0 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_pmu_stereo_standalone_copy_ros_01 | 162.16 | 未采样 | 仅 VINS | 94.69 / 82.38 | 未采样 |
| native_pmu_stereo_standalone_share_ros_02 | 162.93 | 未采样 | 仅 VINS | 96.55 / 82.73 | 未采样 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/pmu/)

四类事件在本机均可用，time_running / time_enabled 为 1，无复用缩放。计数覆盖 VINS 原生进程及继承线程的用户态，包括启动、退出和短暂 Python gate；与资源采样的 subscription-ready-to-drain 窗口不同

| 入口 | cycles (十亿) | instructions (十亿) | cache references (十亿) | cache misses (十亿) | IPC | misses / 千条指令 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| copy | 669.518 | 1128.723 | 21.976 | 2.639 | 1.686 | 2.338 |
| share | 668.862 | 1128.692 | 22.125 | 2.589 | 1.687 | 2.294 |

两轮完整接收左右各 3682 张图像、36820 条 IMU，处理 3682 帧，各一次初始化，无重置/配对丢弃，轨迹逐字节一致，进程均正常退出。CPU 分别为 162.16 / 162.93 秒，单轮差异不支持稳定提速结论；灰度 share 入口零物化仍由入口计数单独证明

cache misses 是 CPU 缓存诊断事件，不能换算为 DDR 字节或功耗。本机未发现 DDR 控制器事件；CPU 能量节点存在但当前用户不可读，二者均记不可用。未改 PMU 逻辑，仅修正旧报告中的虚拟化主机描述

<!-- native-phase:shared -->
## 跨进程 ROS Image 与 memfd 对照

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_shared_stereo_split_share_ros_01 | stereo_imu_vio / split / ros/share | 1831 / 1819 | 0.252745 | 0.003083 | 188.31 / 6.01 | 0 |
| native_shared_stereo_split_share_memfd_02 | stereo_imu_vio / split / memfd/share | 1831 / 1819 | 0.252745 | 0.003083 | 188.21 / 6.01 | 0 |
| native_shared_mono_split_share_ros_03 | mono_imu_vio / split / ros/share | 1831 / 1819 | 0.185564 | 0.002938 | 188.20 / 6.00 | 0 |
| native_shared_mono_split_share_memfd_04 | mono_imu_vio / split / memfd/share | 1831 / 1819 | 0.185564 | 0.002938 | 188.15 / 6.01 | 0 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_shared_stereo_split_share_ros_01 | 165.88 | 2.97 | 168.85 | 82.18 / 71.47 | 95.86 / 85.86 |
| native_shared_stereo_split_share_memfd_02 | 164.59 | 3.03 | 167.62 | 76.81 / 65.78 | 27.50 / 17.00 |
| native_shared_mono_split_share_ros_03 | 109.81 | 1.72 | 111.53 | 77.77 / 67.25 | 61.50 / 51.39 |
| native_shared_mono_split_share_memfd_04 | 109.97 | 1.82 | 111.79 | 73.16 / 62.42 | 27.04 / 16.70 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/shared/)

四轮均采用 split、share、1 倍目标供给及同一原生 Cyclone DDS 默认 XML，配置 SHA256 为 `85e5760fd50150fae47b4d24f0cc48230445eb7507de840e1fac74bfae4be7e1`。本机默认配置已完成两种模式的完整 ROS Image 回放；历史 WSL 小分片参数未启用，不将旧网络故障作为本机事实

左右图/IMU/处理计数完整，各一次初始化，无重置或配对丢弃，1831 个位姿、1819 个匹配，末帧覆盖完整，两个进程均退出 0。同模式下 ROS Image/memfd 轨迹及全帧像素/原始时间戳摘要一致，轨迹也与前阶段相同；消费端灰度入口物化均为零

| memfd 模式 | 源端复制帧数 | 源端复制量 (MiB) | 消费端校验帧数 | 槽位复用 | 池满等待 | 未归还 / 错误 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| stereo_imu | 7364 | 2534.97 | 7364 | 7361 | 0 | 0 / 0 |
| mono_imu | 3682 | 1267.49 | 3682 | 3680 | 0 | 0 / 0 |

memfd 源端与消费端为不同 PID，双方 peer 凭据一致；注册时消费端逐槽核验 fd 的 device/inode/尺寸，日志记录前两槽身份。图像尺寸 752×480、stride 752；32 槽位经代次与 owner 归还协议复用。EuRoC 解包后仍向池中复制一次像素，不能称为端到端零拷贝

双目合计 CPU 为 ROS 168.85 / memfd 167.62 秒，单目为 111.53 / 111.79 秒；单次方向不一致，稳定收益留待重复统计。源端 PSS 峰值分别为双目 85.86 / 17.00 MiB、单目 51.39 / 16.70 MiB，是本次观测；每进程峰值分别记录，不能相加作为同时峰值

回放墙钟约 188 秒，包含启动/完成观察；约 6 秒排空含固定等待，不是逐帧延迟或实时通过证明。上述资源结果包含双方全帧 SHA256 校验成本，DDR/CPU 功耗仍不可用

本阶段最小改动为显式原生 DDS 默认 XML、实际 XML 冻结，以及重复执行器的配置/设备参数和排空时间记录。VINS C++、依赖、算法参数与二进制未改；新 tag 为 `milestone-ros2-shared-memory-native-ubuntu22-v1`

<!-- native-phase:vgem -->
## VGEM DMA-BUF 原生完整回放

| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| native_vgem_stereo_split_share_vgem_01 | stereo_imu_vio / split / vgem/share | 1831 / 1819 | 0.252745 | 0.003083 | 188.20 / 6.01 | 0 |
| native_vgem_mono_split_share_vgem_02 | mono_imu_vio / split / vgem/share | 1831 / 1819 | 0.185564 | 0.002938 | 188.15 / 6.00 | 0 |

CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收

| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |
| --- | ---: | ---: | ---: | --- | --- |
| native_vgem_stereo_split_share_vgem_01 | 437.90 | 2.97 | 440.87 | 78.93 / 68.84 | 26.40 / 16.41 |
| native_vgem_mono_split_share_vgem_02 | 242.68 | 1.90 | 244.58 | 73.38 / 62.86 | 26.42 / 16.44 |

[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/vgem/)

两轮 VGEM 使用前阶段相同的原生默认 DDS XML、share 入口、1 倍目标供给和全帧 SHA256 校验，VINS/数据源二进制及标定、算法参数均相同。代码提交号由 `24fd362` 变为 `dd68d8d`，变化为文档、执行器和显式配置归档，不是算法或传输 C++ 修改

| VGEM 模式 | 源端复制帧数 | 源端复制量 (MiB) | 消费端校验帧数 | 槽位复用 | 池满等待 | 未归还 / 错误 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| stereo_imu | 7364 | 2534.97 | 7364 | 7359 | 0 | 0 / 0 |
| mono_imu | 3682 | 1267.49 | 3682 | 3679 | 0 | 0 / 0 |

设备重新查询为 `/dev/dri/card0`、vgem 1.0.0，当前用户可读写。独立 PID 的双方 peer 凭据一致，消费端注册时逐槽核验 DMA-BUF 的 device/inode/尺寸，日志记录前两槽身份；752×480、stride 752，分配大小 364544 字节。现有协议执行 CPU 读写 START/END 同步、代次检查和 owner 归还，两轮均无错误或未归还槽位

单目/双目均完整处理 3682 帧、接收 36820 条 IMU，双目左右各 3682 张、单目右图为 0；各一次初始化、无重置/配对丢弃，1831 个位姿、1819 个匹配，覆盖末帧且两个进程退出 0。同模式下 ROS Image/memfd/VGEM 的输入摘要和轨迹字节全部一致

| 模式 | ROS Image 合计 CPU (s) | memfd 合计 CPU (s) | VGEM 合计 CPU (s) | VGEM VINS / 源端 CPU (s) |
| --- | ---: | ---: | ---: | --- |
| stereo_imu | 168.85 | 167.62 | 440.87 | 437.90 / 2.97 |
| mono_imu | 111.53 | 111.79 | 244.58 | 242.68 / 1.90 |

**本机 VGEM 正确性通过，但这两轮 CPU 代价明显高于 ROS/memfd，增加主要在 VINS 消费进程**。逐秒原始采样的 CPU 增量与 run.json 一致；回放仍约 188 秒、排空约 6 秒、无池满等待。现有进程采样不能分离映射像素访问、SHA256 校验和跟踪计算的具体代价，不将原因归于未经验证的缓存机制，也不为得到预期收益关闭校验或改算法；后续五次重复保持实现不变

VGEM 是软件 DMA-BUF 分配/CPU 映射机制验证，未使用 GPU 计算、相机 DMA、RGA 或板端 fence；EuRoC 源端仍复制一次到池。DDR/CPU 功耗不可用，不能用 CPU 差异或逻辑复制量替代。新 tag 为 `milestone-ros2-dmabuf-native-ubuntu22-v1`

<!-- experiment:native_shared_repeats_20261013 -->
## EuRoC 串行重复实验：native_shared_repeats_20261013

新增 30 次完整实验：单目/双目，各传输独立重复 5 次；不包含此前六次试跑。
每轮仅一个数据源和一个 VINS；上一轮完成、退出、评估后再启动下一轮。顺序轮换，每轮间隔 10.0 秒。
同一冻结二进制、MH_01_easy 输入/标定、1 倍目标供给、统一且冻结的 Cyclone DDS 配置、share 入口和全像素 SHA256 校验；无回环/RViz

| 模式 | 传输 | n | 合计 CPU 秒中位数 [Q25, Q75] | CPU 秒范围 | 回放秒中位数 | ATE RMSE 中位数 (m) | 同轮对照 CPU 变化中位数 |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: |
| stereo_imu | ros | 5 | 167.91 [167.59, 168.08] | 167.21–168.52 | 188.31 | 0.252745 | +0.00% |
| stereo_imu | memfd | 5 | 167.83 [167.70, 168.05] | 167.12–168.30 | 188.18 | 0.252745 | -0.05% |
| stereo_imu | vgem | 5 | 442.28 [442.16, 442.41] | 441.15–443.00 | 188.16 | 0.252745 | +163.33% |
| mono_imu | ros | 5 | 110.90 [110.79, 111.34] | 110.12–111.54 | 188.18 | 0.185564 | +0.00% |
| mono_imu | memfd | 5 | 111.36 [111.13, 111.56] | 111.09–112.25 | 188.17 | 0.185564 | +0.41% |
| mono_imu | vgem | 5 | 244.76 [243.46, 245.54] | 242.55–246.57 | 188.14 | 0.185564 | +120.26% |

CPU 秒是数据源与 VINS 所有线程累计 CPU 时间之和；负的对照变化表示省 CPU。回放墙钟含启动与完成通知观察，目标 1 倍不能保证无背压。
五轮顺序轮换缓解顺序偏差，但不构成完全平衡设计；未固定宿主频率/温度，不能据此宣称统计显著或外推 RK3588。
原始 CSV/summary.json 还记录两进程分别的 CPU、RSS/PSS 峰值、排空时间、池满等待与 ATE/RPE；两个独立 PSS 峰值不能相加当作同时峰值。
每轮原始资源采样含 Linux 主机负载和 PSI；宿主指标包含其他程序。SHA256 校验的线程位置随路径不同，结果包含校验成本。
各轮完整处理、干净退出、全像素/时间戳一致和共享槽位归还均已通过；DDR 流量和功耗未实测

[本轮 30 次实验快照](../infra/desktop/comparison_reference/native_shared_repeats_20261013/)

重复批次历时 10:01:04–11:43:59 UTC（约 102.9 分钟），无失败轮次。独立核验 353 个冻结文件未变，全部输入/末帧、一次初始化、零重置/配对丢弃、退出和共享槽位归还通过；同模式 15 轮轨迹字节一致，并与前阶段一致。共享路径 20 轮全部零池满等待。每轮原始 CPU 增量与采样 CSV 一致，统计分布已重新计算核对

| 模式 / 传输 | VINS / 源端 CPU 中位数 (s) | VINS RSS / PSS 峰值中位数 (MiB) | 源端 RSS / PSS 峰值中位数 (MiB) | 回放 / 排空中位数 (s) |
| --- | --- | --- | --- | --- |
| stereo_imu / ros | 164.91 / 2.92 | 81.34 / 70.82 | 96.26 / 86.27 | 188.307 / 6.007 |
| stereo_imu / memfd | 164.82 / 3.01 | 78.25 / 67.59 | 27.55 / 17.04 | 188.183 / 6.006 |
| stereo_imu / vgem | 439.29 / 2.94 | 78.22 / 67.75 | 26.48 / 16.50 | 188.164 / 6.006 |
| mono_imu / ros | 109.17 / 1.67 | 76.13 / 66.05 | 61.55 / 51.43 | 188.176 / 6.007 |
| mono_imu / memfd | 109.54 / 1.81 | 74.94 / 63.09 | 27.08 / 16.75 | 188.166 / 6.006 |
| mono_imu / vgem | 242.84 / 1.91 | 72.51 / 61.99 | 26.36 / 16.38 | 188.140 / 6.005 |

每列是五轮内各进程独立峰值/时间的中位数，CPU 分项中位数之和不一定等于合计中位数；RSS/PSS 不能相加视为同时峰值。完整 Q25/Q75/范围、RPE 和逐轮数据保存在 summary.json、trials.csv；回放含启动/观察，排空含约 6 秒固定等待，不是逐帧实时延迟验收

**本机结论：memfd 没有明确合计 CPU 收益，VGEM 的高 CPU 代价在五次重复中持续出现**。同轮相对 ROS 的 CPU 变化中位数分别为 memfd 双目 −0.05%、单目 +0.41%，VGEM 双目 +163.33%、单目 +120.26%；不能沿用旧 WSL 性能收益。VGEM 的增加主要位于 VINS 消费端，具体操作归因未定位，没有通过关闭校验或修改算法消除这个结果

源端 PSS 峰值中位数在 ROS/memfd/VGEM 下为双目 86.27 / 17.04 / 16.50 MiB、单目 51.43 / 16.75 / 16.38 MiB；本机共享路径的源端内存观测较低，VINS PSS 差异见表。源端仍有一次像素复制，包含全像素 SHA256 校验成本，不能据此称全链路零拷贝或外推板端缓存、DDR、功耗结果

三路径全部使用同一原生默认 DDS XML（SHA256 `85e5760fd50150fae47b4d24f0cc48230445eb7507de840e1fac74bfae4be7e1`）、source commit `511f08f`、同一 VINS/数据源二进制。新 annotated tag 为 `milestone-ros2-shared-repeats-native-ubuntu22-v1`，直接提交到 ros2-humble

<!-- native-phase:handoff -->
## 原生桌面交接核验

全部 52 轮回放验收完成。18 份实验 SHA256 清单共 1308 条通过，另冻结交接证据 8 条，历史 609 个快照 blob 与原 b250dc0 一致，八个原 annotated tag 与远端一致。源码/参数未改，隔离动态库、脚本与文档入口复核通过；PMU 恢复 4、VGEM 已卸载、无残留 VINS/播放器

新增只读归档核验脚本处理历史两种路径约定，不改写原清单。失败摘录的来源和覆盖边界仍保留，文档整理未重跑 VIO。新 annotated tag 为 `milestone-ros2-desktop-handoff-native-ubuntu22-v1`，直接提交于 ros2-humble

[交接核验证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/handoff/)，板端、真实相机和硬件加速仍需分别验收

## RK3588 profile 工具验收（2026-10-14）

目标为 RK3588S / Ubuntu 22.04.5 / 厂商内核 5.10.110。系统原先无 perf；联网主机从锁定 ARM Ubuntu 包提取 perf，打包 11 个非 glibc 动态库，经 C++ 远端工具部署、采样并回收。工具版本实测为 5.15.216，不替换内核或板端 glibc，PMU 权限保持原值 2

| 验证项 | 结果 |
| --- | --- |
| task-clock / cycles / instructions / cache-references / cache-misses | 五类用户态事件成功，计数运行比例 100%，无不支持/未计数 |
| cycles:u / 99 Hz / frame-pointer 栈 | 298 个样本，丢样为 0 |
| 函数符号 | profile_work 解析成功，测试热点占 99.96% |
| 依赖与退出 | ldd 无缺库，远端退出 0 |

[本阶段证据及 SHA256](../infra/rk3588/reference/perf_20261014/)，重建与运行入口见第 08 份文档。这里只证明 CPU profile 工具可用，不代表 VINS 热点或性能结论；DDR 字节/秒与 CPU 功耗仍不可用，不用 cache misses 代替

板端墙上时钟尚未同步，perf 文件头与远端 start_utc 的日期不作为主机 UTC。回放/采样耗时按单调时钟统计，外层阶段事件按主机 UTC 归档，本轮未修改板端系统时间

## RK3588 固定版本视觉库验收（2026-10-14）

主机 GCC 11.4.0 交叉编译 OpenCV 4.2.0 / Ceres 1.14.0 / Eigen 3.3.9 后，通过固定 C++ 远端工具部署 ARM 探针及 25 个动态库；板端正常退出 0、ldd 无缺库，仍使用板端 glibc/loader

OpenCV 在步长 80 字节的 64×64 灰度图上检测八个角点，LK 位移误差均小于 0.1 像素，输入图像未修改。Ceres 分别使用 SuiteSparse/CXSparse 执行 SPARSE_NORMAL_CHOLESKY，两次均求得 x=10；启用宏集合与桌面 Ceres 一致，包含 LAPACK、SuiteSparse、CXSparse 和 OpenMP。这是依赖运行验收，尚无板端 VINS 轨迹或性能结果

| 传递依赖 | 原生 x86 | ARM SDK |
| --- | --- | --- |
| SuiteSparse / CXSparse | 5.10.1 / 3.2.0 | 5.10.1 / 3.2.0 |
| glog / gflags | 0.6.0 / 2.2.2 | 0.4.0 / 2.2.2 |
| BLAS | OpenBLAS 0.3.34 | Netlib 3.10.0 |

保留指定 OpenCV/Ceres/Eigen 版本和求解器功能，传递依赖使用 ARM Ubuntu 包；后续跨主机性能差异不能仅归因于架构。更正旧失败归档关于 SuiteSparse 版本不同的错误描述，两端实际均 5.10.1；原冻结文件与哈希保留，更正说明及实测见 [视觉库证据](../infra/rk3588/reference/legacy_20261014/)

前期 GCC 参数、SDK alternatives 与绝对符号链接问题的失败证据单独保存，均未运行 VINS、不计入成功实验统计。最终 sysroot 内链接已修正并完整重建，消费者链接和板端实际计算均已通过

## RK3588 ARM ROS 2 构建与全局事件核对（2026-10-14）

ros2-build04 在独立 ros2_ws_overlay 完成 cv_bridge 与四个项目 package 的交叉构建。四个主节点的递归依赖共 76 个 ARM ELF，运行库均可找到，只包含 OpenCV 4.2 SONAME；cv_bridge_DIR/camera_models_DIR 指向重建前缀，未选择 SDK OpenCV 4.5。此阶段验收的是主机构建与 ELF 闭包，尚未执行板端节点或 VIO，不提供轨迹、CPU 或实时性结论

同次核对一次性读取全部 52 个 event/state、覆盖 29 个阶段，确认配对记录无不一致；板端 13 个阶段已统一归类，两次退出 0 的不合格构建未接受为成功。主机无活动任务，板端七个先前作业均已结束；桌面 19 份清单/1316 条哈希、板端原有 14 份清单/103 条哈希及 1276 个桌面交接快照文件核验通过，核心/config 与 7d42fac 一致

[全局证据和事件路径/SHA256 账本](../infra/rk3588/reference/global_audit_20261014/)，当前有效产物与迟到通知处理规则见 [第 10 份说明](10_PHASE_EVENT_AUDIT.md)。下一项仅使用已核验的 ros2_ws_overlay/install 与 legacy 部署，不复用旧混链产物

## RK3588 ROS 2 运行环境验收（2026-10-14）

runtime01 通过固定 scp/远端工具部署运行包，板端校验 6991 个文件 SHA256；rclpy、sensor_msgs、composition_interfaces、rosbag2_py 在板端 Python 3.10.12 导入成功。Cyclone DDS 下，独立 VINS 节点及组件均创建完整双目/IMU 订阅，组件加载/卸载成功，独立节点与容器退出均为 0。ldd 无缺库，实际进程 maps 仅出现运行包 OpenCV 4.2；主机外层事件也退出 0

运行包未包含静态库、KITTI 程序或 SDK cv_bridge/OpenCV 4.5，保留板端 glibc/loader。核心和 config 与干净交叉构建 c0ae27d 一致，逐文件清单、动态库 maps、节点日志与事件见 [运行环境证据](../infra/rk3588/reference/runtime_20261014/)。没有 bag 输入，计数为零，本阶段没有轨迹、ATE/RPE 或 VINS 性能结论

Fast DDS 后端补充验收 fastrtps02：四个已验签索引锁定 ARM 包、50 个 addon 文件及 6991 个原运行文件哈希通过。Fast DDS 2.6.12 / rmw_fastrtps 6.2.10 下独立节点和组件订阅就绪、组件卸载成功、两进程退出 0，实际 maps 显示 addon RMW 及原 OpenCV 4.2。原 SDK/运行包保持不变，[证据及 SHA256](../infra/rk3588/reference/fastrtps_20261014/)。此前基线启动缺该后端、HTTPS 下载证书失败均保留，尚未启动 VINS，不计为成功回放

## RK3588 ROS 2 完整双目基线（2026-10-14）

board-baseline02 完整回放通过，standalone/copy/ROS Image/Fast DDS、rate=1，OpenCV 4.2.0 / Ceres 1.14.0，保留原标定与算法参数。两路图像各 3682、IMU 36820、processed 3682，一次初始化，无重置或配对丢帧；末帧覆盖，VINS/回放均退出 0，板端结束审计无旧作业活进程。原运行包、addon 和输入 bag 哈希均通过

| 指标 | 板端一轮实测 |
| --- | --- |
| 姿态 / 真值匹配 | 1831 / 1819 |
| ATE RMSE，SE(3) 无尺度校正 | 0.269229 m |
| RPE RMSE，一姿态步长 | 0.00313946 m |
| VINS 全线程 CPU | 673.68 s，订阅就绪至排空 |
| VINS RSS / PSS 采样峰值 | 83.72 / 73.05 MiB |
| 回放 / 排空等待 | 188.43 / 6.12 s |
| 温度观测 | 各 thermal_zone 整轮最高 60.08 °C |
| CPU 频率观测 | A55 408–1800 MHz，两个 A76 policy 均 408–2352 MHz |
| DDR 带宽 / CPU 功耗 | 不可用 |

原 standalone runner 只采 VINS，未采 ros2 bag play 的 CPU/RSS/PSS；673.68 s 不能当作合计 CPU。composed 统计容器内 VINS+源端，split 分别记录两进程，比较时保留不同范围。温度/频率覆盖启动、回放及排空，不据频率变化单独判定降频原因；dmc 528–1560 MHz 是频率，不是带宽

评估在主机同一 uv.lock/evo 环境执行。板端轨迹与 x86 双目参照不同，未宣称跨架构字节一致或将差异归因于单一因素；传递依赖差异见前表。排空包含稳定采样等待，完整消费与末帧成功不是逐帧实时延迟验收。本轮只有一次实际完整回放，旧启动失败不计入成功实验；[完整证据、轨迹图与 SHA256](../infra/rk3588/reference/baseline_20261014/)

## RK3588 单目与组件/owner 对照（2026-10-14）

board-components01 新增五轮，各配置一次；双目 standalone/copy 复用上节基线，不重复实验。全轮输入计数完整、末帧覆盖，初始化一次、无重置/配对丢帧，1831 个姿态 / 1819 个匹配，VINS/容器及回放均退出 0。主机 uv.lock/evo 自动评估完成，板端结束审计无旧任务活进程

| 模式 / 部署 / 入口 | ATE / RPE RMSE (m) | 全线程 CPU (s) | RSS / PSS 峰值 (MiB) | 回放 / 排空 (s) |
| --- | --- | ---: | --- | --- |
| stereo / standalone / share | 0.264430 / 0.003120 | 672.82 | 82.08 / 71.67 | 188.52 / 6.12 |
| mono / standalone / copy | 0.162089 / 0.003012 | 559.08 | 73.08 / 62.69 | 188.73 / 6.11 |
| mono / standalone / share | 0.159856 / 0.003038 | 558.32 | 72.03 / 61.97 | 188.72 / 6.12 |
| stereo / composed / copy | 0.265527 / 0.003124 | 678.97 | 69.99 / 65.60 | 188.49 / 6.10 |
| stereo / composed / share | 0.266425 / 0.003112 | 675.81 | 71.33 / 66.56 | 188.36 / 6.11 |

standalone CPU/RSS/PSS 只含 VINS，composed 是容器内 VINS+typed player；不跨范围相减推断通信开销。对应 share 相对 copy 单轮 CPU 为双目 standalone −0.128%、单目 standalone −0.136%、双目 composed −0.465%，均不足 0.5%；一次观察没有确定提速结论。各轮轨迹有小幅差异，不能沿用桌面同模式字节一致结论，差异原因尚未定位，未修改算法或参数消除它

share 灰度入口物化次数/字节均为 0，双目共享入口 7364、单目 3682；copy 分别物化 14728 / 7364 次、5,316,218,880 / 2,658,109,440 字节。composed 前六条消息样本源端/消费端 message 和 pixel 指针一致，copy 的 Mat 另有像素存储，share 的 Mat 借用原像素。这是已有 owner/入口的板端证据，不代表真实相机、DMA heap 或端到端零拷贝

运行包、addon、bag 与核心/config 固定，完整日志及资源、telemetry、逐轮评估与解压前日志 SHA256 见 [归档](../infra/rk3588/reference/components_20261014/)。大日志 gzip 保存，原日志仍在工作区；排空含稳定等待，DDR 带宽/功耗仍不可用
