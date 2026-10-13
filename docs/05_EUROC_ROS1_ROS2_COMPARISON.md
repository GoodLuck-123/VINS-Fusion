# 原生 Ubuntu 22.04 EuRoC 复现实测

本页只记录当前物理主机实测。WSL 原报告保存在历史 tag；历史归档及冻结哈希保持原样

主机：Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，16 逻辑 CPU、约 30 GiB 内存

输入为相同 SHA256 的 MH_01_easy；OpenCV 4.2.0、Ceres 1.14.0、标定及算法参数保持原版。evo 使用 IMU/body 真值、SE(3) 对齐、不校正尺度，相邻位姿 RPE 约 0.1 秒间隔

DDR 流量不可用；CPU 能量节点默认不可读。GPU hwmon 功率不代表 CPU VIO 功耗

ROS 1 四轮、ROS 2 两轮参照、八轮组件/owner、两轮 PMU、四轮共享传输及两轮 VGEM 已完成，累计 52 轮；完整回放复现已结束，最终交接核验继续。完整清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

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
