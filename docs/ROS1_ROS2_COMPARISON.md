# ROS 1 / ROS 2 EuRoC 对比实验

日期：2026-10-09

两轮均值：ATE ROS 1 为 0.252696 m、ROS 2 为 0.252744 m；平均 CPU 占用分别为 151.93% / 152.74%；RSS 峰值均值分别为 76.40 / 90.45 MiB。本序列精度接近，CPU 差异较小；ROS 2 的内存开销更高。

`master` 保留 ROS 1；`ros2-humble` 是独立的 ROS 2 Humble 版本。
实验在 Ubuntu 22.04.5 / WSL2 / x86_64 串行运行；顺序为 ROS 1 → ROS 2 → ROS 2 → ROS 1。

使用 MH_01_easy，双目 IMU，完整 1 倍速；不运行回环/GNSS/RViz。
OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、GCC 13.4、配置和标定保持一致。
ROS 2 所需的 cv_bridge 3.2.1 / C++17 以及中间件是记录在案的接口与运行时差异。

全部图像像素、IMU 数值/协方差和原始时间戳逐消息校验一致；完整校验和依赖路径记录见参照快照。

## 精度与完整性

| 版本 / 轮次 | poses | 匹配率 | ATE RMSE (m) | 相邻位姿 RPE RMSE (m) | 回放耗时 (s) | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 1831 | 99.34% | 0.252745 | 0.003083 | 188.32 | -6 |
| ros1 / 2 | 1831 | 99.34% | 0.252646 | 0.003081 | 188.37 | -6 |
| ros2 / 1 | 1831 | 99.34% | 0.252744 | 0.003083 | 188.43 | 0 |
| ros2 / 2 | 1831 | 99.34% | 0.252745 | 0.003083 | 188.44 | 0 |

ATE 使用保持尺度的 SE(3) 对齐，时间匹配容差 0.01 s；RPE 是相邻 pose，间隔约 0.1 s。
匹配率不足 100% 主要来自真值未覆盖的序列尾部。末帧覆盖检查通过，日志无配对丢弃或 failure detection。
ROS 2 每轮收到左右图像各 3682、IMU 36820，处理图像对 3682。
ROS 1 的 -6 是原版未 join 同步线程导致的退出 abort；完整回放状态分别记录。ROS 2 的后台线程和全局发布器显式销毁。

## 节点资源压力

| 版本 / 轮次 | CPU 秒 | 平均单核 CPU (%) | CPU p95 (%) | RSS 峰值 (MiB) | PSS 峰值 (MiB) | 线程峰值 | 主缺页 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 290.94 | 150.49 | 181.76 | 76.21 | 67.42 | 25 | 0 |
| ros1 / 2 | 296.61 | 153.38 | 185.69 | 76.59 | 68.17 | 25 | 0 |
| ros2 / 1 | 298.11 | 154.11 | 195.43 | 88.39 | 75.97 | 32 | 0 |
| ros2 / 2 | 292.82 | 151.36 | 184.59 | 92.50 | 80.08 | 30 | 0 |

CPU 以一个逻辑核为 100%，包含节点全部线程；窗口从订阅就绪到回放后稳定，含启动延迟和稳定等待。
p95 来自约 1 s 的 CPU 采样，不能解读为单帧处理延迟。完整 RSS/PSS、缺页、I/O、主线程上下文切换和系统压力记录在每轮 resources.csv / run.json。

## I/O 和传输压力

| 版本 / 轮次 | 进程物理读 (MiB) | 进程物理写 (MiB) | 主线程自愿切换 | 主线程非自愿切换 | 主机 loopback RX 增量 (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| ros1 / 1 | 0.000 | 0.398 | 20124 | 12 | 0.000 |
| ros1 / 2 | 0.000 | 0.398 | 19622 | 12 | 0.000 |
| ros2 / 1 | 0.000 | 0.398 | 20025 | 72 | 0.075 |
| ros2 / 2 | 0.000 | 0.398 | 19694 | 45 | 0.077 |

ros1 输入序列化数据量 / 图像时间跨度：约 13.835 MiB/s（逻辑输入压力，不是实测链路带宽）。

ros2 输入序列化数据量 / 图像时间跨度：约 13.837 MiB/s（逻辑输入压力，不是实测链路带宽）。

物理 I/O 受页缓存影响；rchar/wchar 也不是内存带宽。主机 loopback / PSI 包含其他进程，且 WSL 网络计数可能无法反映传感器传输，不用它们推断 DDR 或零拷贝收益。
当前未采集内存控制器带宽、硬件 cycles/cache misses、温度或功耗，也未添加前后端细粒度计时。

## 结论边界与复现

两轮结果用于本机迁移参照与发现回归，不能建立多序列精度容差或宣称统计性能提升；没有调整算法参数来追平指标。
回环/GNSS 的完整数据功能、KITTI 数据及 RViz 尚未验收；三个主节点的无输入启动和正常退出、KITTI 参数检查已通过。

[搭建与实验命令](UBUNTU22_ROS2_SETUP.md)；[版本化参照快照](../infra/desktop/ros2_reference/)。原始日志在仓库父目录的 results/，不纳入 Git。

<!-- experiment:components_images_20261010 -->
## 组件化与图像所有权：单目/双目 A/B（2026-10-10）

本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。
使用 MH_01_easy 完整 1 倍速回放；未运行回环/GNSS/RViz。

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

copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。
前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制。

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

以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制。

同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS。

stereo_imu_vio / standalone / rmw_fastrtps_cpp：copy/share 轮数 2/2，CPU 均值 150.48% / 152.76%，RSS 峰值均值 90.27 / 90.99 MiB。

mono_imu_vio / standalone / rmw_fastrtps_cpp：copy/share 轮数 1/1，CPU 均值 93.51% / 93.04%，RSS 峰值均值 82.67 / 83.90 MiB。

stereo_imu_vio / composed / rmw_cyclonedds_cpp：copy/share 轮数 1/1，CPU 均值 152.31% / 153.27%，RSS 峰值均值 75.64 / 75.66 MiB。

standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。
composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。
composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比。

MH01_stereo_composed_copy2：6 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；入口视图复制像素符合所选路径。全序列共享数量另见上表。

MH01_stereo_composed_share1：6 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；入口视图共享像素符合所选路径。全序列共享数量另见上表。

各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。
少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速。

本轮未实施跨进程共享内存、相机 DMA-BUF、RGA、NEON 或全程序零拷贝；未测 DDR 带宽和功耗。

[本节参照快照](../infra/desktop/comparison_reference/components_images_20261010/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv。

本轮判断：单目视惯与双目视惯共用组件/图像接口，均已完整验证。独立入口双目四轮 ATE 均约 0.252745 m，单目 copy/share 的 ATE 均为 0.185564 m。单目更小的误差只代表本序列观察，不能推导单目总体优于双目；本轮也没有新增 ROS 1 单目参照。

双目独立入口 share 的 CPU 均值比 copy 高 2.29 个百分点（相对约 1.52%），RSS 峰值均值高约 0.72 MiB；当前不能声称整机性能改善。单目 CPU 从 93.51% 到 93.04% 仅各一轮，也不足以证明提速。组件数据源 copy 的 ATE 为 0.256757 m，比 share 高约 0.004013 m（约 1.59%）；未定位这项差异的具体来源，不宣称两个部署路径的轨迹完全等同。没有通过修改求解器预算、特征数或输入频率追平结果。

已确定的收益是原生灰度入口显式物化次数降至零：单目每轮减少 7364 次、约 2.48 GiB 累计像素复制；双目减少 14728 次、约 4.95 GiB。这里是累计复制数据量，不是峰值占用或 DDR 带宽实测。

补充的入口微基准使用同一张 752×480 mono8 热缓存图像，预热 100 次后按 copy → share → share → copy 顺序，每组 2000 次。copy 两组均值约 172.90 μs/图，share 约 0.0783 μs/图。只覆盖适配器，不含 DDS、跟踪或后端；其局部耗时降低不能转换为整机加速比。探针不入 Git，结果、输入尺寸、适配器/探针哈希保存在 [微基准记录](../infra/desktop/comparison_reference/components_images_20261010/image_ingress_benchmark.json)。

组件生命周期测试完成双目 → 单目 → 双目 → 单目的加载/卸载，并核验重复实例拒绝、无效配置拒绝和容器正常退出。为控制改动，上游全局配置/发布器仍保留，一个进程限一个 VINS 估计器；可与 EuRoC 数据源组件共存。

本机默认 Fast DDS 下动态加载服务请求未完成，标准 ROS 服务也复现；组件实验明确使用锁文件中已有的 Cyclone DDS。问题未定位或修复，不能外推为 Fast DDS 在其他机器不可用。独立节点实验保持原始 Fast DDS。组件运行命令及 RMW 切换见 [环境文档](UBUNTU22_ROS2_SETUP.md#组件入口)。

本地所有权探针覆盖 mono8/8UC1、padding stride、颜色转换回退、无效 stride、消息存活、输入只读及五帧双目 copy/share 特征一致性。ASan 仅插桩适配器/测试可执行文件，未对所有依赖库插桩，关闭泄漏检查；其初始化期故障经 GDB 定位到 main 前的加载器/ASan 初始化，仅测试进程设置 LD_BIND_NOW=1 后连续三次通过。不能据此宣称全程序无泄漏。证据见同一快照内 ownership_checks.json、component_smoke.json 和 smoke.json。

以上八轮使用源码 00658b0；随后 70c0b3b 仅补齐组件公开头文件的依赖导出，增量构建后 VINS/组件二进制哈希保持一致。完整构建和隔离检查通过，仍加载独立 ROS 2 前缀中的 OpenCV 4.2.0 / Ceres 1.14.0。历史参照快照未改写，未来版本继续在本文末尾追加。
