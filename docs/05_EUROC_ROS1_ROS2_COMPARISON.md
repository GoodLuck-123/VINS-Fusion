# ROS 1 / ROS 2 EuRoC 对比实验

本文按实验阶段保留历史记录，后续版本继续在末尾追加；候选工作安排见 [x86 CPU 实验计划](06_X86_CPU_EXPERIMENTS.md)

- 原版迁移：[精度与完整性](#精度与完整性)、[节点资源压力](#节点资源压力)
- 组件与测量：[图像所有权 A/B](#组件化与图像所有权单目双目-ab2026-10-10)、[DDR/功耗及 PMU](#ddr功耗可测性核验与-cpu-pmu-对照2026-10-10)
- 跨进程传输：[memfd 首轮](#euroc-双进程共享像素ros-image--memfd单目双目)、[VGEM 首轮](#euroc-真实-vgem-dma-buf与-ros-image--memfd-对照)、[30 次串行重复实验](#euroc-串行重复实验shared_repeats_20261010)

日期：2026-10-09

两轮均值：ATE ROS 1 为 0.252696 m、ROS 2 为 0.252744 m；平均 CPU 占用分别为 151.93% / 152.74%；RSS 峰值均值分别为 76.40 / 90.45 MiB。本序列精度接近，CPU 差异较小；ROS 2 的内存开销更高

`master` 保留 ROS 1；`ros2-humble` 是独立的 ROS 2 Humble 版本。实验在 Ubuntu 22.04.5 / WSL2 / x86_64 串行运行；顺序为 ROS 1 → ROS 2 → ROS 2 → ROS 1

使用 MH_01_easy，双目 IMU，完整 1 倍速；不运行回环/GNSS/RViz。OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、GCC 13.4、配置和标定保持一致。ROS 2 所需的 cv_bridge 3.2.1 / C++17 以及中间件是记录在案的接口与运行时差异

全部图像像素、IMU 数值/协方差和原始时间戳逐消息校验一致；完整校验和依赖路径记录见参照快照

## 精度与完整性

| 版本 / 轮次 | poses | 匹配率 | ATE RMSE (m) | 相邻位姿 RPE RMSE (m) | 回放耗时 (s) | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 1831 | 99.34% | 0.252745 | 0.003083 | 188.32 | -6 |
| ros1 / 2 | 1831 | 99.34% | 0.252646 | 0.003081 | 188.37 | -6 |
| ros2 / 1 | 1831 | 99.34% | 0.252744 | 0.003083 | 188.43 | 0 |
| ros2 / 2 | 1831 | 99.34% | 0.252745 | 0.003083 | 188.44 | 0 |

ATE 使用保持尺度的 SE(3) 对齐，时间匹配容差 0.01 s；RPE 是相邻 pose，间隔约 0.1 s。匹配率不足 100% 主要来自真值未覆盖的序列尾部。末帧覆盖检查通过，日志无配对丢弃或 failure detection。ROS 2 每轮收到左右图像各 3682、IMU 36820，处理图像对 3682。ROS 1 的 -6 是原版未 join 同步线程导致的退出 abort；完整回放状态分别记录。ROS 2 的后台线程和全局发布器显式销毁

## 节点资源压力

| 版本 / 轮次 | CPU 秒 | 平均单核 CPU (%) | CPU p95 (%) | RSS 峰值 (MiB) | PSS 峰值 (MiB) | 线程峰值 | 主缺页 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 290.94 | 150.49 | 181.76 | 76.21 | 67.42 | 25 | 0 |
| ros1 / 2 | 296.61 | 153.38 | 185.69 | 76.59 | 68.17 | 25 | 0 |
| ros2 / 1 | 298.11 | 154.11 | 195.43 | 88.39 | 75.97 | 32 | 0 |
| ros2 / 2 | 292.82 | 151.36 | 184.59 | 92.50 | 80.08 | 30 | 0 |

CPU 以一个逻辑核为 100%，包含节点全部线程；窗口从订阅就绪到回放后稳定，含启动延迟和稳定等待。p95 来自约 1 s 的 CPU 采样，不能解读为单帧处理延迟。完整 RSS/PSS、缺页、I/O、主线程上下文切换和系统压力记录在每轮 resources.csv / run.json

## I/O 和传输压力

| 版本 / 轮次 | 进程物理读 (MiB) | 进程物理写 (MiB) | 主线程自愿切换 | 主线程非自愿切换 | 主机 loopback RX 增量 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 0.000 | 0.398 | 20124 | 12 | 0.000 |
| ros1 / 2 | 0.000 | 0.398 | 19622 | 12 | 0.000 |
| ros2 / 1 | 0.000 | 0.398 | 20025 | 72 | 0.075 |
| ros2 / 2 | 0.000 | 0.398 | 19694 | 45 | 0.077 |

ros1 输入序列化数据量 / 图像时间跨度：约 13.835 MiB/s（逻辑输入压力，不是实测链路带宽）

ros2 输入序列化数据量 / 图像时间跨度：约 13.837 MiB/s（逻辑输入压力，不是实测链路带宽）

物理 I/O 受页缓存影响；rchar/wchar 也不是内存带宽。主机 loopback / PSI 包含其他进程，且 WSL 网络计数可能无法反映传感器传输，不用它们推断 DDR 或零拷贝收益。当前未采集内存控制器带宽、硬件 cycles/cache misses、温度或功耗，也未添加前后端细粒度计时

## 结论边界与复现

两轮结果用于本机迁移参照与发现回归，不能建立多序列精度容差或宣称统计性能提升；没有调整算法参数来追平指标。回环/GNSS 的完整数据功能、KITTI 数据及 RViz 尚未验收；三个主节点的无输入启动和正常退出、KITTI 参数检查已通过

[搭建与实验命令](04_UBUNTU22_ROS2_SETUP.md)；[版本化参照快照](../infra/desktop/ros2_reference/)。原始日志在仓库父目录的 results/，不纳入 Git

<!-- experiment:components_images_20261010 -->
## 组件化与图像所有权：单目/双目 A/B（2026-10-10）

本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。使用 MH_01_easy 完整 1 倍速回放；未运行回环/GNSS/RViz

| 实验 | 模式 / 部署 | RMW | 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| MH01_stereo_copy1 | stereo_imu_vio / standalone | fastrtps_cpp | copy | 1831 | 0.252745 | 0.003083 | 150.66 | 89.57 |
| MH01_stereo_share1 | stereo_imu_vio / standalone | fastrtps_cpp | share | 1831 | 0.252745 | 0.003083 | 152.32 | 91.14 |
| MH01_stereo_share2 | stereo_imu_vio / standalone | fastrtps_cpp | share | 1831 | 0.252745 | 0.003083 | 153.21 | 90.84 |
| MH01_stereo_copy2 | stereo_imu_vio / standalone | fastrtps_cpp | copy | 1831 | 0.252745 | 0.003083 | 150.29 | 90.98 |
| MH01_mono_copy1 | mono_imu_vio / standalone | fastrtps_cpp | copy | 1831 | 0.185564 | 0.002938 | 93.51 | 82.67 |
| MH01_mono_share1 | mono_imu_vio / standalone | fastrtps_cpp | share | 1831 | 0.185564 | 0.002938 | 93.04 | 83.90 |
| MH01_stereo_composed_copy2 | stereo_imu_vio / composed | cyclonedds_cpp | copy | 1831 | 0.256757 | 0.003097 | 152.31 | 75.64 |
| MH01_stereo_composed_share1 | stereo_imu_vio / composed | cyclonedds_cpp | share | 1831 | 0.252744 | 0.003083 | 153.27 | 75.66 |

copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制

| 实验 | 左 / 右 / IMU / 处理图像 | 共享图像 | 入口物化次数 | 入口物化数据 (MiB) |
| --- | --- | ---: | ---: | ---: |
| MH01_stereo_copy1 | 3682 / 3682 / 36820 / 3682 | 0 | 14728 | 5069.94 |
| MH01_stereo_share1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_stereo_share2 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_stereo_copy2 | 3682 / 3682 / 36820 / 3682 | 0 | 14728 | 5069.94 |
| MH01_mono_copy1 | 3682 / 0 / 36820 / 3682 | 0 | 7364 | 2534.97 |
| MH01_mono_share1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |
| MH01_stereo_composed_copy2 | 3682 / 3682 / 36820 / 3682 | 0 | 14728 | 5069.94 |
| MH01_stereo_composed_share1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |

以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制

同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS

stereo_imu_vio / standalone / rmw_fastrtps_cpp：copy/share 轮数 2/2，CPU 均值 150.48% / 152.76%，RSS 峰值均值 90.27 / 90.99 MiB

mono_imu_vio / standalone / rmw_fastrtps_cpp：copy/share 轮数 1/1，CPU 均值 93.51% / 93.04%，RSS 峰值均值 82.67 / 83.90 MiB

stereo_imu_vio / composed / rmw_cyclonedds_cpp：copy/share 轮数 1/1，CPU 均值 152.31% / 153.27%，RSS 峰值均值 75.64 / 75.66 MiB

standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比

MH01_stereo_composed_copy2：6 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；入口视图复制像素符合所选路径。全序列共享数量另见上表

MH01_stereo_composed_share1：6 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；入口视图共享像素符合所选路径。全序列共享数量另见上表

各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速

本轮未实施跨进程共享内存、相机 DMA-BUF、RGA、NEON 或全程序零拷贝；未测 DDR 带宽和功耗

[本节参照快照](../infra/desktop/comparison_reference/components_images_20261010/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv

本轮判断：单目视惯与双目视惯共用组件/图像接口，均已完整验证。独立入口双目四轮 ATE 均约 0.252745 m，单目 copy/share 的 ATE 均为 0.185564 m。单目更小的误差只代表本序列观察，不能推导单目总体优于双目；本轮也没有新增 ROS 1 单目参照

双目独立入口 share 的 CPU 均值比 copy 高 2.29 个百分点（相对约 1.52%），RSS 峰值均值高约 0.72 MiB；当前不能声称整机性能改善。单目 CPU 从 93.51% 到 93.04% 仅各一轮，也不足以证明提速。组件数据源 copy 的 ATE 为 0.256757 m，比 share 高约 0.004013 m（约 1.59%）；未定位这项差异的具体来源，不宣称两个部署路径的轨迹完全等同。没有通过修改求解器预算、特征数或输入频率追平结果

已确定的收益是原生灰度入口显式物化次数降至零：单目每轮减少 7364 次、约 2.48 GiB 累计像素复制；双目减少 14728 次、约 4.95 GiB。这里是累计复制数据量，不是峰值占用或 DDR 带宽实测

补充的入口微基准使用同一张 752×480 mono8 热缓存图像，预热 100 次后按 copy → share → share → copy 顺序，每组 2000 次。copy 两组均值约 172.90 μs/图，share 约 0.0783 μs/图。只覆盖适配器，不含 DDS、跟踪或后端；其局部耗时降低不能转换为整机加速比。探针不入 Git，结果、输入尺寸、适配器/探针哈希保存在 [微基准记录](../infra/desktop/comparison_reference/components_images_20261010/image_ingress_benchmark.json)

组件生命周期测试完成双目 → 单目 → 双目 → 单目的加载/卸载，并核验重复实例拒绝、无效配置拒绝和容器正常退出。为控制改动，上游全局配置/发布器仍保留，一个进程限一个 VINS 估计器；可与 EuRoC 数据源组件共存

本机默认 Fast DDS 下动态加载服务请求未完成，标准 ROS 服务也复现；组件实验明确使用锁文件中已有的 Cyclone DDS。问题未定位或修复，不能外推为 Fast DDS 在其他机器不可用。独立节点实验保持原始 Fast DDS。组件运行命令及 RMW 切换见 [环境文档](04_UBUNTU22_ROS2_SETUP.md#组件入口)

本地所有权探针覆盖 mono8/8UC1、padding stride、颜色转换回退、无效 stride、消息存活、输入只读及五帧双目 copy/share 特征一致性。ASan 仅插桩适配器/测试可执行文件，未对所有依赖库插桩，关闭泄漏检查；其初始化期故障经 GDB 定位到 main 前的加载器/ASan 初始化，仅测试进程设置 LD_BIND_NOW=1 后连续三次通过。不能据此宣称全程序无泄漏。证据见同一快照内 ownership_checks.json、component_smoke.json 和 smoke.json

以上八轮使用源码 00658b0；随后 70c0b3b 仅补齐组件公开头文件的依赖导出，增量构建后 VINS/组件二进制哈希保持一致。完整构建和隔离检查通过，仍加载独立 ROS 2 前缀中的 OpenCV 4.2.0 / Ceres 1.14.0。历史参照快照未改写，未来版本继续在本文末尾追加

<!-- experiment:pmu_capabilities_20261010 -->
## DDR/功耗可测性核验与 CPU PMU 对照（2026-10-10）

本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。使用 MH_01_easy 完整 1 倍速回放；未运行回环/GNSS/RViz

| 实验 | 模式 / 部署 | RMW | 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| MH01_stereo_pmu_copy1 | stereo_imu_vio / standalone | fastrtps_cpp | copy | 1831 | 0.252750 | 0.003083 | 165.76 | 91.50 |
| MH01_stereo_pmu_share1 | stereo_imu_vio / standalone | fastrtps_cpp | share | 1831 | 0.252710 | 0.003083 | 176.71 | 93.88 |

| 实验 | cycles (十亿) | instructions (十亿) | cache misses (百万) | IPC | misses / 千条指令 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MH01_stereo_pmu_copy1 | 910.289 | 1111.060 | 2044.252 | 1.221 | 1.840 |
| MH01_stereo_pmu_share1 | 931.805 | 1110.565 | 2152.260 | 1.192 | 1.938 |

CPU PMU 统计用户态及继承的工作线程，含启动/退出及短暂门控；与 subscription-ready-to-drain 的资源采样窗口不同。表中仅显示无计数器轮换的事件；原始 time_enabled/time_running 和错误保存在 run.json。WSL 虚拟化 PMU 的 IPC/cache misses 仅用于诊断，不是 DDR 流量、memory-bound 判定或功耗实测

copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制

| 实验 | 左 / 右 / IMU / 处理图像 | 共享图像 | 入口物化次数 | 入口物化数据 (MiB) |
| --- | --- | ---: | ---: | ---: |
| MH01_stereo_pmu_copy1 | 3682 / 3682 / 36820 / 3682 | 0 | 14728 | 5069.94 |
| MH01_stereo_pmu_share1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |

以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制

同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS

stereo_imu_vio / standalone / rmw_fastrtps_cpp：copy/share 轮数 1/1，CPU 均值 165.76% / 176.71%，RSS 峰值均值 91.50 / 93.88 MiB

standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比

各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速

本轮未实施跨进程共享内存、相机 DMA-BUF、RGA、NEON 或全程序零拷贝；未测 DDR 带宽和功耗

[本节参照快照](../infra/desktop/comparison_reference/pmu_capabilities_20261010/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv

本轮只增加测量工具，VINS/组件二进制与上一节一致，没有改算法、依赖、回环开关或图像频率。两轮都完整接收左右各 3682 张图像、36820 条 IMU，正常退出。指令数从 1.111060 万亿到 1.110565 万亿（约 -0.045%），cycles 从 910.289 十亿到 931.805 十亿（约 +2.36%），cache misses 从 2044.252 百万到 2152.260 百万（约 +5.28%）。本轮没有显示缓存/执行压力下降；各一轮且未控制宿主调度、温控和频率，不定位为算法回归，不建立性能显著性结论。计数器可能引入开销，不能与此前不带 PMU 的 CPU 表直接计算加速比

**进程与线程。** 正式实验均未启动 loop_fusion/global_fusion/RViz，是开环 VIO。standalone 和仅 VINS component 的业务链各有两个进程：VINS（或组件容器）及外部播放器；composed 把数据源和 VINS 放进同一容器，业务链只有一个进程。另有 Python runner（订阅观察与采样），以及启动 shell/controller 等辅助进程，它们不属于原表的 VINS 资源采样。一个进程含一个或多个线程，共享地址空间；进程 CPU 统计累计全部线程，线程数不能解释为同时占用的核数。上一节 VINS 双目线程采样峰值 31–32、单目 29–31，同进程容器峰值 31，包含 DDS、计算库及 VINS 工作线程

**RSS 峰值。** RSS 是进程当前驻留在物理内存中的页面总量，包含代码、栈、图像、求解器对象及共享库等；表中峰值取约 1 秒采样的最大值，可能错过短峰。run.json 另有 VmHWM 高水位参考；proc 驻留核算有延迟，采样 RSS 与 VmHWM 不必完全吻合。RSS 不是累计分配或 DDR 搬运，共享页面相加可能重复计算，多进程可同时看 PSS。一个峰值不能证明泄漏；后续长回放关注预热后的持续增长，再针对异常 debug。[Linux proc 说明](https://docs.kernel.org/filesystems/proc.html)

**减拷贝预期。** 复制本身消耗 CPU 指令、缓存读写和分配，减少它也可能降低 CPU 时间、DDR 压力和功耗。但逻辑复制不一定到 DDR：缓存命中会减少外存访问，写分配/回写又可能增加访问，不能直接把复制字节当作 DDR 流量。CPU 占用也不是有效算术单元利用率。若瓶颈是访存等待，减少争用可能提高有效吞吐；仍需热点/profile 才能证明 VINS 是 memory bound。固定 1 倍速供给适合完整性和资源对照，不能单凭它测出最大吞吐

**DDR 与功耗目前未测得。** WSL2 / i5-1135G7 暴露 CPU PMU，但没有 IMC/DDR/DFI 事件、RAPL energy_uj 或物理 hwmon 功率输入，/dev/cpu 也不存在。power PMU 的 events 目录为空；BAT1 标注 Microsoft Hyper-V Virtual Battery，power_now 为 0，不能解释为实验功耗为零。Windows 宿主的 PATH 工具查找及运行进程查找未发现现成 PCM/HWiNFO/VTune 读数入口；未做全盘安装扫描或安装驱动

因此 DDR 读/写字节、能量和平均功率保留 null，不用 cache_misses×64、rchar/wchar 或累计复制字节替代。证据见 [能力清单](../infra/desktop/comparison_reference/pmu_capabilities_20261010/hardware_probe_20261010_verified.json)；CPU 计数器的 inherit 机制见 [Linux 接口](https://man7.org/linux/man-pages/man2/perf_event_open.2.html)

真正测量需要物理主机上支持该 CPU 的内存控制器计数器，或目标板的 DFI/DMC/BSP 接口；事件到字节的换算由硬件文档决定。[Intel PCM](https://github.com/intel/pcm) 是可评估的 Windows 宿主路径，实际 CPU/驱动支持项须核验。功耗用有效能量差/时间算平均功率，没有板端传感器则用输入电源仪表。RAPL package/DRAM 是硬件域，不能称作某个进程的独占能耗，也不等于整板/插座功率。[Linux RAPL 接口](https://docs.kernel.org/power/powercap/powercap.html)

后续物理平台 A/B 应统一整个数据源 + VINS 链、供给频率、预热和计时区间，记录宿主空闲及数据源背景，交替顺序重复；报告 DDR read/write MiB/s、累计字节、能量 J、平均/峰值 W 和每帧能量。空闲差分用于估计增量，同时保留原始读数。长期泄漏排查随实际实验推进，不以峰值或局部 ASan 代替全程序验收

**共享内存与 DMA-BUF 的通用性。** 工作量详见 [任务书补充评估](01_RK3588_DEPLOYMENT_PLAN.md#共享内存与-dma-buf-的补充评估2026-10-10)。现有 mono8/8UC1 视图与相机品牌解耦，但不消除 SDK 到 ROS 消息的复制；颜色转换/压缩解码仍有必要输出。换相机仍需更新标定、时间戳和噪声参数

DDS 共享内存传输和 Data-sharing 是两层机制，不能都称作零拷贝。当前 Fast DDS 为 2.6.10；Data-sharing 要求 bounded 类型，完整零拷贝还限制 plain 类型。标准 Image 有可变长像素数组、encoding/header 字符串，仅开启 SHM 无法自动获得端到端零拷贝

[Data-sharing](https://fast-dds.docs.eprosima.com/en/2.6.x/fastdds/transport/datasharing.html)、[零拷贝条件](https://fast-dds.docs.eprosima.com/en/2.6.x/fastdds/use_cases/zero_copy/zero_copy.html)、[Image 定义](https://github.com/ros2/common_interfaces/blob/humble/sensor_msgs/msg/Image.msg)

真正跨进程共享像素估计 2–4 人周：采用区域/偏移/代次描述符和共享 owner，处理尺寸上限、prev_img 持有、慢消费者、崩溃回收和重连。协议可复用于图像、深度和点云，但生产者/消费者都需适配。若 SDK 不能写入共享池，SDK → 池仍可能复制一次，后续消费者可共享；普通 Image、bag、RViz 和远端网络保留边界转换。IMU/GNSS 数据较小，先保持标准消息

已有 DMA-BUF 驱动的单相机接入约 1–2 人周；连同 RGA 和跨进程句柄约 2–4 人周，包含前者基础，不简单相加。DMA-BUF 可作为跨进程共享像素的底层，两者并非二选一。能力取决于驱动/SDK，不能仅凭 USB/MIPI 判断。要传递真实 fd 句柄（例如 Unix socket SCM_RIGHTS），不能只在 ROS topic 里发 fd 数字或进程指针；同时协商格式、planes、offset/stride、同步和归还。普通共享内存不自动成为 RGA 可用 DMA 缓冲

硬件写完后 CPU 才能读，所有消费者包括 prev_img 完成后才归还相机；封闭 SDK 无接口时不保证无复制。[Linux DMA-BUF](https://docs.kernel.org/driver-api/dma-buf.html)、[布局协商](https://docs.kernel.org/userspace-api/dma-buf-alloc-exchange.html)、[V4L2 导出](https://www.kernel.org/doc/html/v4.9/media/uapi/v4l/vidioc-expbuf.html)

建议保持算法层只读图像及 owner 规则，在数据源层分别接 ROS Image、共享内存和 DMA-BUF：支持则共享，不匹配则明确回退。Rockchip 已有 fd 导入示例，但 cache 同步本身也可能产生 CPU 负载，不能预设自动提速。[RGA 示例](https://github.com/airockchip/librga/blob/main/samples/allocator_demo/src/rga_allocator_dma32_demo.cpp)、[RGA FAQ](https://github.com/airockchip/librga/blob/main/docs/Rockchip_FAQ_RGA_EN.md)

<!-- experiment:shared_memory_20261010 -->
## EuRoC 双进程共享像素：ROS Image / memfd（单目、双目）

本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。使用 MH_01_easy 完整 1 倍速回放；未运行回环/GNSS/RViz

| 实验 | 模式 / 部署 | RMW | 传输 / 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| MH01_stereo_split_ros_tuned1 | stereo_imu_vio / split | cyclonedds_cpp | ros / share | 1831 | 0.251245 | 0.003099 | 292.74 | 132.89 |
| MH01_stereo_split_memfd_tuned1 | stereo_imu_vio / split | cyclonedds_cpp | memfd / share | 1831 | 0.253811 | 0.003087 | 186.79 | 78.82 |
| MH01_mono_split_ros_tuned1 | mono_imu_vio / split | cyclonedds_cpp | ros / share | 1831 | 0.185562 | 0.002938 | 102.77 | 75.60 |
| MH01_mono_split_memfd_tuned1 | mono_imu_vio / split | cyclonedds_cpp | memfd / share | 1831 | 0.185560 | 0.002938 | 106.60 | 81.09 |

本节 split 每轮均运行两个独立原生进程：同一个 typed EuRoC 数据源 + VINS。ROS 对照也启用全像素 SHA256，使用相同时间戳、数据源、Cyclone DDS 和线程/算法配置。上表 CPU/RSS 为 VINS 单进程；下表包含数据源，CPU 之和以共同观测墙钟归一。SHA256 每张图像在数据源、消费端各计算一次，CPU 数值包含校验成本

三条路径使用相同的进程级 cyclonedds_wsl.xml（1400 B 数据报上限、1024 B 分片）；WSL 镜像网络的大包故障诊断单独归档。小分片会增加 DDS 开销，不能把本机省去 DDS 图像路径的 CPU 收益外推为 ARM/DDR/功耗提升。共享路径消费端校验在线程接收处，ROS 对照校验在同步入口，因此调度与执行阶段仍有差异。PSS 较适合共享页比较；各进程独立采样峰值之和不是同时峰值，也不是 DDR 用量

| 实验 | 数据源 CPU 秒 | 两进程 CPU 秒 | 两进程平均 CPU (%) | VINS / 数据源 PSS 峰值 (MiB) | 逐帧校验 | 数据源显式像素复制 (MiB) |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| MH01_stereo_split_ros_tuned1 | 89.39 | 656.73 | 338.86 | 120.83 / 86.64 | 全帧通过 | 未统计 DDS 内部复制 |
| MH01_stereo_split_memfd_tuned1 | 29.33 | 391.26 | 201.92 | 66.87 / 18.29 | 全帧通过 | 2534.97 |
| MH01_mono_split_ros_tuned1 | 16.82 | 215.91 | 111.46 | 63.63 / 51.74 | 全帧通过 | 未统计 DDS 内部复制 |
| MH01_mono_split_memfd_tuned1 | 18.85 | 225.34 | 116.33 | 66.15 / 22.04 | 全帧通过 | 1267.49 |

每摄像头累计 SHA256 包括每帧原始 header 时间戳和逐行有效像素摘要，忽略行尾填充；数据源与消费端一致，且同模式的三种传输应一致。memfd 是普通共享像素；vgem 为内核 DRM 导出的真实 DMA-BUF。通过 SCM_RIGHTS 传递内核句柄，在独立 PID 内导入并核验 device/inode/长度，消费端只读 mmap；不传裸指针或 fd 数字

32 个有界槽位记录代次，缓冲用完会阻塞；归还发生在当前与上一左帧 owner 全部释放之后。DMA-BUF CPU 读写各有 START/END 同步，无硬件 DMA/fence/RGA 参与本次回放。bag 反序列化仍分配图像；共享数据源每帧仍复制一次到池中。此次消除的是跨进程图像消息的序列化/像素搬运路径及 VINS 入口复制，不是全链路零拷贝，也没有完整统计 DDS 内部复制次数

| 实验 | 池复用次数 | 池满等待次数 | 退出未归还槽位 | 源端 / 消费端错误 | 独立进程句柄核验 |
| --- | ---: | ---: | ---: | --- | --- |
| MH01_stereo_split_memfd_tuned1 | 7355 | 0 | 0 | 0 / 0 | 通过 |
| MH01_mono_split_memfd_tuned1 | 3650 | 133 | 0 | 0 / 0 | 通过 |

池为每轮重新创建，停止后关闭 fd、解除映射、删除本轮 socket；源码及本地 ASan 压力证据补充生命周期核验，未进行长时间故障恢复验收

copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制

| 实验 | 左 / 右 / IMU / 处理图像 | 共享图像 | 入口物化次数 | 入口物化数据 (MiB) |
| --- | --- | ---: | ---: | ---: |
| MH01_stereo_split_ros_tuned1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_stereo_split_memfd_tuned1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_mono_split_ros_tuned1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |
| MH01_mono_split_memfd_tuned1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |

以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制

同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS

standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比

各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速

本轮实现 EuRoC 跨进程共享像素与可选 VGEM DMA-BUF；相机 DMA、RGA、NEON、全程序零拷贝未实施，DDR 带宽和功耗未实测

[本节参照快照](../infra/desktop/comparison_reference/shared_memory_20261010/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv

共享内存里程碑结论：四轮全部处理 3682 帧左图与 36820 条 IMU，双目右图同为 3682，均输出 1831 个后端位姿，正常退出。两种传输同模式输入签名一致；双目 ATE 0.251245 / 0.253811 m，单目 0.185562 / 0.185560 m，未观察到跟踪失败或配对丢弃。两进程 CPU 秒：双目 ROS/memfd 为 656.73 / 391.26，单目为 215.91 / 225.34。单目没有 CPU 收益，不能把双目的结果视作普遍加速；这轮只有各一遍

memfd 单目出现 133 次池满等待，退出未归还槽位为 0；这是背压而非丢弃，完整 1 倍速回放与末帧覆盖通过。次数不提供等待时长或单帧尾延迟证明，后续实际相机需测队列龄期、生产者阻塞时长及长期运行。消费端入口物化为 0，但源端每图仍复制一次：双目累计 2534.97 MiB、单目 1267.49 MiB；这些不是 DDR 实测字节

本里程碑源码冻结于 `95d02e1`（后续归档提交不改算法/二进制）。环境动态库审计、两后端各 1000 帧局部 ASan 压力验证及失败启动记录在上述快照；ASan 未覆盖全部依赖，fork 子进程在析构后 `_exit`，未运行子进程 LeakSanitizer 收尾。VGEM 的完整 EuRoC 验收另列下一节，不能用本节 memfd 结果代替。版本回退与历史 tag 见 [环境文档](04_UBUNTU22_ROS2_SETUP.md#版本里程碑与切换)

<!-- experiment:dmabuf_20261010 -->
## EuRoC 真实 VGEM DMA-BUF：与 ROS Image / memfd 对照

本节新增 VGEM 单目/双目两轮；ROS/memfd 四份对照复用上一节结果，合计六次完整实验，表格复用不计为新回放

本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。使用 MH_01_easy 完整回放，目标供给倍率为 1；背压可能延长实际墙钟时间，不能以配置倍率证明实时性。未运行回环/GNSS/RViz

| 实验 | 模式 / 部署 | RMW | 传输 / 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| MH01_stereo_split_ros_tuned1 | stereo_imu_vio / split | cyclonedds_cpp | ros / share | 1831 | 0.251245 | 0.003099 | 292.74 | 132.89 |
| MH01_stereo_split_memfd_tuned1 | stereo_imu_vio / split | cyclonedds_cpp | memfd / share | 1831 | 0.253811 | 0.003087 | 186.79 | 78.82 |
| MH01_stereo_split_vgem_tuned1 | stereo_imu_vio / split | cyclonedds_cpp | vgem / share | 1831 | 0.252658 | 0.003083 | 333.61 | 76.25 |
| MH01_mono_split_ros_tuned1 | mono_imu_vio / split | cyclonedds_cpp | ros / share | 1831 | 0.185562 | 0.002938 | 102.77 | 75.60 |
| MH01_mono_split_memfd_tuned1 | mono_imu_vio / split | cyclonedds_cpp | memfd / share | 1831 | 0.185560 | 0.002938 | 106.60 | 81.09 |
| MH01_mono_split_vgem_tuned1 | mono_imu_vio / split | cyclonedds_cpp | vgem / share | 1831 | 0.185564 | 0.002938 | 183.88 | 69.02 |

本节 split 每轮均运行两个独立原生进程：同一个 typed EuRoC 数据源 + VINS。ROS 对照也启用全像素 SHA256，使用相同时间戳、数据源、Cyclone DDS 和线程/算法配置。上表 CPU/RSS 为 VINS 单进程；下表包含数据源，CPU 之和以共同观测墙钟归一。SHA256 每张图像在数据源、消费端各计算一次，CPU 数值包含校验成本

三条路径使用相同的进程级 cyclonedds_wsl.xml（1400 B 数据报上限、1024 B 分片）；WSL 镜像网络的大包故障诊断单独归档。小分片会增加 DDS 开销，不能把本机省去 DDS 图像路径的 CPU 收益外推为 ARM/DDR/功耗提升。共享路径消费端校验在线程接收处，ROS 对照校验在同步入口，因此调度与执行阶段仍有差异。PSS 较适合共享页比较；各进程独立采样峰值之和不是同时峰值，也不是 DDR 用量

| 实验 | 数据源 CPU 秒 | 两进程 CPU 秒 | 两进程平均 CPU (%) | VINS / 数据源 PSS 峰值 (MiB) | 逐帧校验 | 数据源显式像素复制 (MiB) |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| MH01_stereo_split_ros_tuned1 | 89.39 | 656.73 | 338.86 | 120.83 / 86.64 | 全帧通过 | 未统计 DDS 内部复制 |
| MH01_stereo_split_memfd_tuned1 | 29.33 | 391.26 | 201.92 | 66.87 / 18.29 | 全帧通过 | 2534.97 |
| MH01_stereo_split_vgem_tuned1 | 27.84 | 734.64 | 346.75 | 65.86 / 16.40 | 全帧通过 | 2534.97 |
| MH01_mono_split_ros_tuned1 | 16.82 | 215.91 | 111.46 | 63.63 / 51.74 | 全帧通过 | 未统计 DDS 内部复制 |
| MH01_mono_split_memfd_tuned1 | 18.85 | 225.34 | 116.33 | 66.15 / 22.04 | 全帧通过 | 1267.49 |
| MH01_mono_split_vgem_tuned1 | 11.62 | 367.55 | 189.88 | 58.65 / 16.50 | 全帧通过 | 1267.49 |

每摄像头累计 SHA256 包括每帧原始 header 时间戳和逐行有效像素摘要，忽略行尾填充；数据源与消费端一致，且同模式的三种传输应一致。memfd 是普通共享像素；vgem 为内核 DRM 导出的真实 DMA-BUF。通过 SCM_RIGHTS 传递内核句柄，在独立 PID 内导入并核验 device/inode/长度，消费端只读 mmap；不传裸指针或 fd 数字

32 个有界槽位记录代次，缓冲用完会阻塞；归还发生在当前与上一左帧 owner 全部释放之后。DMA-BUF CPU 读写各有 START/END 同步，无硬件 DMA/fence/RGA 参与本次回放。bag 反序列化仍分配图像；共享数据源每帧仍复制一次到池中。此次消除的是跨进程图像消息的序列化/像素搬运路径及 VINS 入口复制，不是全链路零拷贝，也没有完整统计 DDS 内部复制次数

| 实验 | 回放墙钟 (s) | 后端稳定等待 (s) |
| --- | ---: | ---: |
| MH01_stereo_split_ros_tuned1 | 188.77 | 6.03 |
| MH01_stereo_split_memfd_tuned1 | 188.74 | 6.02 |
| MH01_stereo_split_vgem_tuned1 | 206.84 | 6.02 |
| MH01_mono_split_ros_tuned1 | 188.69 | 6.02 |
| MH01_mono_split_memfd_tuned1 | 188.69 | 6.02 |
| MH01_mono_split_vgem_tuned1 | 188.55 | 6.02 |

回放墙钟含启动就绪、3 秒预延迟和完成通知观察；同来源对照可比较额外阻塞，不能直接等同于传感器记录时长。稳定等待含统一至少约 6 秒的观测条件

| 实验 | 池复用次数 | 池满等待次数 | 退出未归还槽位 | 源端 / 消费端错误 | 独立进程句柄核验 |
| --- | ---: | ---: | ---: | --- | --- |
| MH01_stereo_split_memfd_tuned1 | 7355 | 0 | 0 | 0 / 0 | 通过 |
| MH01_stereo_split_vgem_tuned1 | 7332 | 3419 | 0 | 0 / 0 | 通过 |
| MH01_mono_split_memfd_tuned1 | 3650 | 133 | 0 | 0 / 0 | 通过 |
| MH01_mono_split_vgem_tuned1 | 3678 | 0 | 0 | 0 / 0 | 通过 |

池为每轮重新创建，停止后关闭 fd、解除映射、删除本轮 socket；源码及本地 ASan 压力证据补充生命周期核验，未进行长时间故障恢复验收

copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制

| 实验 | 左 / 右 / IMU / 处理图像 | 共享图像 | 入口物化次数 | 入口物化数据 (MiB) |
| --- | --- | ---: | ---: | ---: |
| MH01_stereo_split_ros_tuned1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_stereo_split_memfd_tuned1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_stereo_split_vgem_tuned1 | 3682 / 3682 / 36820 / 3682 | 7364 | 0 | 0.00 |
| MH01_mono_split_ros_tuned1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |
| MH01_mono_split_memfd_tuned1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |
| MH01_mono_split_vgem_tuned1 | 3682 / 0 / 36820 / 3682 | 3682 | 0 | 0.00 |

以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制

同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS

standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比

各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速

本轮实现 EuRoC 跨进程共享像素与可选 VGEM DMA-BUF；相机 DMA、RGA、NEON、全程序零拷贝未实施，DDR 带宽和功耗未实测

[本节参照快照](../infra/desktop/comparison_reference/dmabuf_20261010/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv

DMA-BUF 里程碑结论：VGEM 双目/单目分别逐帧核验 7364/3682 张真实 DMA-BUF 图像，源端和消费端每摄像头签名与对应 ROS/memfd 相同；两轮均处理 3682 帧左图、36820 条 IMU，输出 1831 个位姿，1819 个与真值匹配（约 99.34%，真值时段略短），正常退出且所有槽位归还。双目 ATE 0.252658 m，单目 0.185564 m；没有跟踪失败或配对丢弃

本机性能没有支持把 VGEM 设为默认：双目 ROS/memfd/VGEM 的两进程 CPU 时间为 656.73 / 391.26 / 734.64 秒，单目为 215.91 / 225.34 / 367.55 秒。VGEM 双目发生 3419 次池满等待，回放墙钟为 206.84 秒，对照约 188.77 秒；配置倍率虽为 1，实际被背压拉长，因此**未通过稳定 1 倍速实时性验收**。单目 VGEM 回放为 188.55 秒、池满等待为 0，但 CPU 仍更高。完整输入和轨迹验收与性能/实时性验收分开记录，不修改频率或丢弃图像去制造改善

缓存属性是后续定位候选。WSL 6.18 系列的 VGEM 将 `map_wc` 设为 true，[WSL VGEM 源码](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-6.18.y/drivers/gpu/drm/vgem/vgem_drv.c)；上游同系列 shmem helper 据此选择 write-combine 映射，[Linux 6.18 映射实现](https://github.com/torvalds/linux/blob/v6.18/drivers/gpu/drm/drm_gem_shmem_helper.c)

这种映射不等同于普通 memfd 的 CPU 缓存策略，可能增加 CPU 密集读图的成本；本轮未逐项 profile 或直接测 PAT/物理 DDR，不将全部差异归因于该因素。两份源码说明的是该内核系列机制，不是本机模块字节审计。板端应核验 cached heap、相机/ISP/RGA 的缓存与 fence；必要时保留一次 CPU 可缓存物化，不能为零拷贝指标强行牺牲性能

本轮完成的是 Linux 内核 DMA-BUF 的分配、导出、跨进程导入、CPU 同步、只读图像使用和生命周期实验。VGEM 是软件分配器，不是相机采集或 RK3588 RGA；EuRoC 解包后仍复制一次到池。没有验证新相机驱动、硬件 DMA、物理连续约束、异步硬件 fence、热重连、多消费者或长期泄漏。普通 ROS 消息保持默认；memfd/VGEM 为可选实验后端，DMA heap 后端未在本机验收。DDR/能量能力在本轮再次检查，读写字节、能量和功率仍为 null，见本节 hardware_probe_dma_20261010.json，不能用 CPU、RSS、复制量或空的功率读数代替

四个历史 annotated tag 已补齐；两个新里程碑分别归档并标记为 `milestone-ros2-shared-memory-v1`、`milestone-ros2-dmabuf-v1`。最后一轮源提交为共享内存报告提交，六轮实际使用同一 VINS 组件、播放器组件和 DDS XML 哈希，算法及依赖未在轮次之间改变；交叉校验摘要见本节 shared_dmabuf_full_validation_20261010.json。标签按完成目标打，不移动历史标签，不自动推送

新版组件另通过单目/双目各两次加载卸载、重复实例及无效配置拒绝、SIGINT 正常退出；证据为本节 component_smoke_shared_20261010.json。环境审计继续确认仅加载 ROS 2 隔离前缀中的 OpenCV 4.2.0 / Ceres 1.14.0 / OpenSSL，未混入系统 OpenCV 或 ROS 1

## 三路径 30 次串行重复实验：预先固定的方案

批次 `shared_repeats_20261010` 新增 30 次完整 MH_01_easy 实验：ROS Image / memfd / VGEM × 单目视惯 / 双目视惯 × 各 5 次。此前六次试跑已经串行，本次用于评估重复性，不复用旧结果计数

五个重复编号分别使用 ROS→memfd→VGEM、memfd→VGEM→ROS、VGEM→ROS→memfd、VGEM→memfd→ROS、memfd→ROS→VGEM；单目/双目块顺序交替。每个编号下相同模式的 ROS 是对应配对参照。五次无法完全平衡全部六种排列，但每种传输在每个位置出现次数相差最多一次

每轮只启动一个 VINS 和一个数据源，完成回放、退出及 evo 评估后留 10 秒间隔；不并发多个配置。保持已验证的原生二进制、OpenCV 4.2.0、Ceres 1.14.0、算法/标定、输入时间戳、Cyclone DDS XML、目标倍率 1 和全帧 SHA256。每轮前后校验源码、二进制、SDK 动态库和配置哈希；冻结期间不构建。未固定 Windows 宿主温度/频率，不增加 PMU 开销或关闭校验

验收每轮完整传感器计数、轨迹覆盖、源端/消费端像素摘要、正常退出和共享槽位归还；任何失败立即停止并保留现场。全部成功后另节追加 CPU 秒的中位数、四分位数、范围和同编号对照变化，另记录实际墙钟、ATE/RPE、RSS/PSS、池等待及 WSL 负载/PSI。每进程独立峰值不视为同时峰值；没有 DDR 或功耗实测

执行与通知为本地后台程序：正常轮次不调用模型，不在线轮询；仅在批次完成或失败时向原对话触发一次处理请求。调度和统计脚本纳入 Git；回调及开发探针留在忽略的 `.local-tests/`。预定方案不是新的性能结果，完成统计由下一节及对应快照给出

<!-- experiment:shared_repeats_20261010 -->
## EuRoC 串行重复实验：shared_repeats_20261010

新增 30 次完整实验：单目/双目，各传输独立重复 5 次；不包含此前六次试跑。每轮仅一个数据源和一个 VINS；上一轮完成、退出、评估后再启动下一轮。顺序轮换，每轮间隔 10 秒。同一冻结二进制、MH_01_easy 输入/标定、1 倍目标供给、Cyclone DDS 小分片配置、share 入口和全像素 SHA256 校验；无回环/RViz

| 模式 | 传输 | n | 合计 CPU 秒中位数 [Q25, Q75] | CPU 秒范围 | 回放秒中位数 | ATE RMSE 中位数 (m) | 同轮对照 CPU 变化中位数 |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: |
| stereo_imu | ros | 5 | 358.06 [355.51, 366.74] | 350.67–368.05 | 188.71 | 0.252755 | +0.00% |
| stereo_imu | memfd | 5 | 312.89 [312.46, 334.99] | 308.39–356.15 | 188.53 | 0.252745 | -11.99% |
| stereo_imu | vgem | 5 | 644.88 [644.43, 650.42] | 637.35–663.45 | 194.58 | 0.252764 | +80.26% |
| mono_imu | ros | 5 | 200.53 [199.32, 205.26] | 198.58–211.91 | 188.59 | 0.185564 | +0.00% |
| mono_imu | memfd | 5 | 201.81 [190.59, 204.25] | 189.66–208.29 | 188.50 | 0.185564 | -3.61% |
| mono_imu | vgem | 5 | 360.63 [359.89, 374.41] | 359.45–400.97 | 188.48 | 0.185564 | +81.60% |

CPU 秒是数据源与 VINS 所有线程累计 CPU 时间之和；负的对照变化表示省 CPU。回放墙钟含启动与完成通知观察，目标 1 倍不能保证无背压。五轮顺序轮换缓解顺序偏差，但不构成完全平衡设计；未固定宿主频率/温度，不能据此宣称统计显著或外推 RK3588。原始 CSV/summary.json 还记录两进程分别的 CPU、RSS/PSS 峰值、池满等待与 ATE/RPE；两个独立 PSS 峰值不能相加当作同时峰值。每轮原始资源采样含 WSL 主机负载和 PSI；宿主指标包含其他程序，不是 Windows 全机观测。SHA256 校验的线程位置随路径不同，结果包含校验成本。各轮完整处理、干净退出、全像素/时间戳一致和共享槽位归还均已通过；DDR 流量和功耗未实测

[本轮 30 次实验快照](../infra/desktop/comparison_reference/shared_repeats_20261010/)

重复实验结论：双目 memfd 五个同编号对照都省 CPU，变化范围为 −15.91%～−3.23%，配对变化中位数为 −11.99%；可作为本机双目跨进程部署的优化选项。它没有稳定复现此前单次试跑的约 40.4% 收益。先前双目 ROS 单次 CPU 为 656.73 秒，本批五次为 350.67～368.05 秒；二进制、DDS XML 和输入均相同，说明不同时间批次不能当作稳定性能参照。当前证据没有隔离出这项跨批差异的具体原因，不将其归因于并发或某一系统因素

单目 memfd 的五个配对变化为 −1.68%、−3.61%、−4.85%、+4.89%、−4.96%；四次较低，一次较高，波动范围和 ROS 重叠。**目前没有足够证据认定单目存在稳定 CPU 收益或稳定退化**，实验室单目需求仍保留 ROS 路径作为默认。这里的 −3.61% 是“每个重复编号内先算比例，再取五个比例的中位数”；不是两组 CPU 中位数的比值。单独比较两组中位数，201.81 / 200.53 − 1 = +0.64%。两种统计量不矛盾，不能把其中一个表述成另一个

VGEM 每个配对都明显增加 CPU：双目 +77.35%～+83.77%，单目 +79.47%～+89.22%。双目五次都有池满等待，2653～3353 次，回放为 193.58～195.60 秒，对照为 188.69～188.76 秒；仍未通过此前定义的稳定 1 倍供给验收。单目虽然跟上供给，计算成本仍明显更高。此结果支持继续将 VGEM 作为真实 DMA-BUF 功能与生命周期实验后端，不能把它设为当前 CPU 图像处理路径的性能默认。缓存策略/同步开销仍是定位候选，不是本轮已证明的唯一原因；相机硬件直接写入、RK3588 的具体 heap/RGA 流水线需要另测

源端内存变化比单目 CPU 变化更清楚。下表为每轮独立峰值的中位数，单位 MiB；不把两进程的峰值相加，也不解释为 DDR 流量

| 传输 | 双目 VINS PSS | 双目数据源 PSS | 单目 VINS PSS | 单目数据源 PSS |
| --- | ---: | ---: | ---: | ---: |
| ROS Image | 71.17 | 85.95 | 64.07 | 51.57 |
| memfd | 66.61 | 17.34 | 60.23 | 16.95 |
| VGEM | 65.92 | 16.46 | 60.10 | 16.45 |

精度没有观察到实质退化：双目各路径 ATE RMSE 中位数约 0.25275 m，单目约 0.185564 m；这是同一 MH_01_easy 数据集的结果，不是覆盖困难场景的普适精度结论。30 轮各处理 3682 帧左图、36820 条 IMU；双目另有 3682 帧右图，每轮输出 1831 个位姿、1819 个匹配真值。共享路径未归还槽位和错误均为 0，没有跟踪失败或配对丢弃

批次从 2026-10-10 04:08:57 UTC 到 05:53:32 UTC，共 104 分 35 秒；包含 30 轮回放、退出、评估、间隔及归档。事后核验 347 个冻结文件、归档原始文件与本地结果一致、30 轮时间区间不重叠及没有原生进程残留。独立摘要为本节 `validation.json`，追加该摘要后重新生成快照 SHA256 清单；原始结果未修改

完成 hook 成功排入一次请求并回到原对话，没有在实验期间调用模型。其额外显式启动操作与队列自动消费发生竞争，返回 `queued submission not found`，所以本地 state.json 记录了非零通知退出码；这是通知诊断，不是实验失败。没有重发完成消息，原始 hook.log 保留；本地回调已简化为只排队一次，避免下一批同类竞争。回调仍在 Git 忽略目录内

本次重复实验归档里程碑为 `milestone-ros2-shared-repeats-v1`；该 tag 表示重复性与文档审阅完成，不表示单目加速、DDR/功耗或相机硬件 DMA 已验收
