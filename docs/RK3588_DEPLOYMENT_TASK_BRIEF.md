# VINS-Fusion / ROS 2 / RK3588 顶层任务书

更新日期：2026-10-10

## 一、目标与总体结论

以当前个人 fork 为起点，以最小改动完成 ROS 1 → ROS 2，在本地数据验证通过后部署 RK3588；随后用板端测量指导 RGA、NEON 和减拷贝优化。保持算法、标定、默认参数与输入时序，各项优化可独立切换，保留原生 CPU/OpenCV 路径。

优先级：正确迁移与可复现验证 > 冗余复制消除 > 有收益的 RGA 算子 > 自研 NEON。ROS 2 是部署基础，不承诺直接提速；RGA 不能承接全部 OpenCV；NEON 不预设能超过优化后的 OpenCV；零拷贝以消除不必要复制为目标，必要的图像输出与长期存储不强求零复制。

初次评估时已检查本地源码和公开官方资料。源码目录 VINS-Fusion，HEAD 为 be55a93（fix a memory issue），origin 为 GoodLuck-123/VINS-Fusion，初次评估时工作树无修改。初次评估未逐提交证明与上游完全一致，也未构建、回放或运行板端 benchmark；后续基线进展见文末。当前主机 Ubuntu 22.04.5，未发现 /opt/ros；data 下已有约 4.4 GB 的 2025-06-07-06-46-12.bag，其话题、编码、标定与真值尚未核查。以下工期是工程估算，收益是条件判断。

## 二、工作量与收益

估算前提：一名熟悉 C++、ROS 和 Linux 的工程师全职；板卡、可用 BSP、相机和数据可获得；包含构建、验证和必要脚本，不包含驱动从零开发。1 人周 = 5 个工作日。

| 工作项 | 工作量 | 收益判断 |
| --- | --- | --- |
| 原版基线与验证入口 | 0.5–1 人周 | 高确定性，是后续正确性与收益评估的前提 |
| ROS 1 → ROS 2 | 2–4 人周 | 部署/维护价值高，直接性能收益不预设 |
| RK3588 原生 CPU 部署与测量 | 0.5–1 人周 | 确认依赖、瓶颈、调度和温控，价值高 |
| RGA 选择性前处理 | 1–3 人周 | 灰度输入可能接近零收益；彩色、高分辨率更有潜力 |
| NEON 有限热点优化 | 2–5 人周 | 不确定性最高，可能不优于 OpenCV |
| 进程内减拷贝与缓冲复用 | 1–2 人周 | 已有明确切入点，整机收益取决于复制耗时占比 |
| 设备/跨进程零拷贝扩展 | 2–4 人周，可选 | 更依赖驱动、RMW、消息类型和生命周期设计 |

基础范围合计 7–16 人周；加 20%–30% 集成余量，建议预算约 9–21 人周。可选零拷贝扩展另计。完整重写 GFTT/LK/描述子或修改相机驱动需重新估算。ROS 2 阶段按现有四个 package 及运行入口适配估算；若只做 VIO 主链，应明确其余模块为延期项。

收益必须报告局部和端到端两层，不能把各阶段加速比相加。目标占串行耗时 p，局部快 s 倍，理想整体加速为 1/((1-p)+p/s)。例如占比 10% 的部分快 3 倍，整机约快 7%；异步流水线还受排队和带宽影响。优化即使不降延迟，也可能减少 CPU 时间或功耗，需分别衡量。

## 三、源码核查对任务范围的约束

1. VIO 前端是 goodFeaturesToTrack（GFTT）补点和 calcOpticalFlowPyrLK（LK）跟踪；双目及反向检查会重复使用 LK。CLAHE 代码已注释，常规路径按特征点做相机模型反投影，并非逐帧全图 remap。
2. 回环另用 FAST + DVision BRIEF；关键帧生成 80×60 缩略图，BRIEF 内部有 GaussianBlur。不能把回环和 VIO 的特征算法合并估算，也不能用 RGA 缩放替代高斯滤波。
3. 图像入口 getImageFromMsg 有 toCvCopy 后再次 clone；8UC1 分支额外复制 message.data，是明确的减拷贝候选。cv::Mat 普通赋值通常只共享像素，不应全部统计成深拷贝。
4. MULTIPLE_THREAD 模式每帧跟踪，但只将隔帧特征送入后端；双目入口现有配对容差为 3 ms。这些是迁移参照语义，不能通过改变频率、同步或丢帧策略制造性能提升。
5. OpenCV LK 源码已有 ARM NEON / SIMD 优化。自研必须与在板端确认启用优化的 Release OpenCV 对照，而非仅与禁用 SIMD 的版本比较。[3][3]

## 四、实施阶段与交付门槛

### 阶段 0：建立原版参照

冻结代码、依赖、配置、标定、词袋和数据；建立统一构建、回放、轨迹评估和性能记录入口。先检查已有 bag 的图像/IMU/GNSS 话题、时间戳、编码及标定匹配情况。自采数据用于真实输入验证；没有真值时只能评价轨迹一致性和运行表现，不能证明绝对精度。另准备 EuRoC 简单、中等、困难序列作为有真值参照。
交付：可复现 ROS 1 基线及原始结果；以双目 IMU 为暂定主模式，其他受支持模式作为回归范围。

### 阶段 1：ROS 2 最小改造与本地验证

将 catkin/package、节点、消息、发布订阅、参数入口、时间、TF、launch 和 RViz 适配到 ROS 2；保留现有 OpenCV YAML 配置与算法核心。只做依赖兼容所必需的修补，避免同时升级算法或求解器策略。
范围涵盖 camera_models、vins_estimator、loop_fusion、global_fusion 和 KITTI 入口；GNSS 与回环可先不用于主验收，但延期或不支持必须明确。尤其核查 ROS 类型/日志侵入算法库、Ceres API 与 OpenCV 版本兼容。
保持原始 header 时间、双目配对、IMU 积分和后端入队语义；落实 QoS 匹配、use_sim_time、bag 转换、线程安全退出、重启及回放速度。迁移期间保持原线程模型，组件化留到减拷贝阶段。
本地为 Ubuntu 22.04，可先用 Humble；若板端 BSP 支持成熟的 Ubuntu 24.04，优先评估 Jazzy，尽量使本地与板端发行版一致。Humble 支持至 2027-05，Jazzy 至 2029-05，应考虑后续维护窗口。[6][6]
社区仓库只作为补丁和接口参考：zinuok 面向 Foxy 并混有 CUDA 改动，snktshrma 宣称 Humble/ARM，均不能凭 README 或 star 数判断可用。[7][7] [8][8] 若考虑采用，必须审核近期有效维护、CI、相关 issue 闭环和算法差异，并用相同数据复现；未通过前坚持当前仓库自行迁移。
交付与门槛：可复现 ROS 2 构建、运行说明和本地数据回归报告。轨迹与输入处理语义通过后，再进行板端试运行。

### 板端里程碑：原生 CPU 版本先跑通

记录板型、系统、BSP/内核、编译器、OpenCV、Ceres、RMW 和 RGA 版本；运行未加速版本，测前端/后端/通信/可视化耗时、CPU、内存、队列及温控降频。固定分辨率、帧率和大小核调度条件。此里程碑形成各优化的共同参照，本地 x86 结果不能替代板端性能结论。

### 阶段 2：RGA 选择性前处理

将“全部 OpenCV 前处理迁移”收敛为“迁移真实存在、硬件支持、语义可验证且有净收益的算子”。优先考察颜色格式转换，已有缩放/裁剪按用途评估；mono8 可直通，NV12 等可研究 Y 平面，但需确认亮度范围和灰度语义。不能为了使用 RGA 增加无必要转换或修改图像尺寸。
Rockchip 的能力表区分 RK3588 上的 RGA2 与 RGA3，灰度格式及对齐限制不能互相套用。[1][1] [2][2] 以实际驱动/librga、能力查询、imcheck 和样本测试决定后端支持矩阵。RGA 的 impyramind/缩放不能直接视为等价的 OpenCV LK 金字塔，滤波、边界、梯度和布局须验证。
保留 CPU 回退，复用缓冲和导入句柄；计时包含导入、执行完成、等待、缓存同步与复制。若涉及尺寸/裁剪变化，另评估内参调整和精度影响。CLAHE、角点、LK、GaussianBlur、任意 remap 不在默认 RGA 交付范围。
交付与门槛：可切换后端、能力限制及板端 A/B 报告。没有可替代热点或净收益不足时，以结论报告关闭该阶段，不强行扩大改造。

### 阶段 3：NEON 热点试验

先确认 OpenCV 的实际优化路径，再按 profile 选择一个热点试验，优先评估中间结果复用，随后决定是否编写 intrinsics。GFTT 补点频度不固定，LK 可能更值得优化，但由测量决定。回环 BRIEF 另立候选，固定 pattern、bit 顺序和词袋兼容性；不能直接换其他描述子。
对照分为正确性参考、原生优化 OpenCV、自研 NEON；BRIEF 的原始基线是 DVision。保持输入、参数、边界与输出容差一致；记录线程数、编译选项、温度/频率、重复次数和 p50/p95/p99。分别测算子和整机，不以关闭 OpenCV 优化制造优势。
交付与门槛：有限热点实现、benchmark、轨迹回归和回退开关。超过测量噪声且值得维护才纳入默认路径；不成立则保留报告，停止扩大范围。

### 阶段 4：分层减拷贝

缓冲区所有权设计在阶段 1/2 接口确定时前置；低风险冗余复制消除可在板端基线后优先实施，最终统一整合。

#### 4a 基础范围

审计图像入口、回环关键帧、队列、消息构造及可视化的复制/分配量。采用只读共享视图、移动语义和必要缓冲复用；原消息/设备缓冲的 owner 必须存活到最后消费者结束，尤其包括跨帧 prev_img。cv::Mat 引用计数不能自动延长外部 DMA 缓冲的生命周期。长期关键帧与可写分支保留必要复制。

#### 4b 条件扩展

若驱动支持，打通相机 DMA-BUF → RGA → CPU 只读视图，处理 stride、fence、缓存一致性和归还时机。算法必须兼容非连续图像；当前 BRIEF 有连续内存断言，不能把带 padding 的 DMA 图像直接当紧密布局。

#### 4c 按需 ROS 通信优化

同进程组件化与正确所有权传递可减少通信复制。[4][4] 跨进程共享内存和 loaned message 依赖实际 RMW/DDS 与消息类型；标准 Image 有动态字段，借用 API 或启用共享内存不等于端到端零拷贝。[5][5] bag、RViz 和录制的外部订阅也应单独测量。
交付与门槛：复制次数/字节数与分配统计、所有权约定、有界队列/缓冲池及长期运行结果。颜色转换输出、金字塔和描述子属于计算产物，不能算作可直接删除的复制。

## 五、统一验收原则

正确性：同数据、配置、原始时间戳、输入与后端处理频率，比较初始化、ATE/RPE、跟踪丢失、重置、有效帧和回环行为。对具有尺度约束的 VIO/双目采用保持尺度的 SE(3) 对齐，避免 Sim(3) 掩盖尺度退化。先多次运行原版确定自然波动，再冻结容差；5% 相对退化配合合理绝对误差下限可作为讨论起点，不作为未经基线支持的硬指标。

性能：报告持续吞吐、整帧与排队延迟、CPU 时间、RSS、复制/分配量，条件允许时记录功耗。关闭可视化与生产配置分别测；固定硬件/输入条件，不能用超量丢帧掩盖积压。

稳定性：目标输入负载下队列不持续增长、内存无持续泄漏，停止/重启可靠；板端建议至少一小时持续运行，记录温度与频率。

复现：保存版本、脚本、配置和原始数据；优化逐项 A/B 后再测累计版本。每阶段决定继续、缩小或结束范围，收益不足允许保留原生实现。

## 六、待锁定条件与暂不纳入范围

开工锁定板型/BSP、目标系统、相机接口与编码、分辨率/帧率、主运行模式、回环/GNSS需求、已有 bag 标定及是否有真值；同时明确实时性目标（吞吐、延迟、CPU/功耗预算）。这些影响后续估算，但不妨碍先建立本地基线。
暂不同时换特征算法、改求解器、引入 GPU/NPU 或开发完整新相机驱动。若后端才是瓶颈，接受前端加速上限，再单独评估后端工作。

## 七、参考资料（核查日期 2026-10-09）

本地依据：

- [vins_estimator/src/featureTracker/feature_tracker.cpp](../vins_estimator/src/featureTracker/feature_tracker.cpp)
- [vins_estimator/src/rosNodeTest.cpp](../vins_estimator/src/rosNodeTest.cpp)
- [vins_estimator/src/estimator/estimator.cpp](../vins_estimator/src/estimator/estimator.cpp)
- [loop_fusion/src/keyframe.cpp](../loop_fusion/src/keyframe.cpp)
- [loop_fusion/src/ThirdParty/DVision/BRIEF.cpp](../loop_fusion/src/ThirdParty/DVision/BRIEF.cpp)

各 package.xml、CMakeLists.txt 与 config/euroc 配置。

- [Rockchip RGA 官方开发指南][1]
- [Rockchip RGA 官方 FAQ][2]
- [OpenCV LK 官方源码][3]
- [ROS 2 进程内通信设计][4]
- [ROS 2 Jazzy loaned message 官方文档源文件][5]
- [ROS 2 平台与生命周期 REP-2000][6]
- [社区参考 zinuok（Foxy）][7]
- [社区参考 snktshrma（Humble/ARM）][8]

社区仓库目前仅经公开页面初筛，未完成维护活跃度/CI/issue 闭环审计，也未复现其运行结果。分支链接会变化，实施时固定经验证的 commit。本任务书不表示算法迁移或板端验证已完成。

## 当前进展

阶段 0 执行进展（2026-10-09）：Ubuntu 22.04 工程内 ROS 1 隔离环境已建立；OpenCV 4.2.0 / Ceres 1.14.0 保留；EuRoC MH_01_easy 两轮完整 1 倍速双目 IMU 回放和真值评估已通过。`master` 保留 ROS 1 算法源码与参照环境。搭建与实测详见 [Ubuntu 22.04 搭建说明](UBUNTU22_ROS1_BASELINE_SETUP.md)、[原版参照实测报告](BASELINE_REFERENCE_REPORT.md)。

阶段 1 桌面进展（2026-10-09）：独立 `ros2-humble` 分支完成 ROS 2 接口和构建迁移，保持同版本视觉/求解依赖及算法配置；两个版本各完成两轮 MH_01_easy 双目 IMU VIO 对比，包含 CPU、内存、I/O 和调度压力指标。详见 [ROS 2 环境说明](UBUNTU22_ROS2_SETUP.md)、[对比报告](ROS1_ROS2_COMPARISON.md)。回环/GNSS/KITTI/RViz 的完整数据验收、其他 EuRoC 序列及板端工作尚未完成。

阶段 4a/4c 桌面进展（2026-10-10）：按当前需求提前完成 VINS 组件入口、图像 owner 跨帧持有及同进程 EuRoC 数据源，保留独立节点和 copy 回退。单目视惯作为实验室目标模式已完整验证；新增八轮单目/双目 A/B，结果统一追加到同一对比报告。原生灰度入口的冗余深拷贝消除、同进程消息地址一致性已验证，但双目整机 CPU 未体现收益；不得等同于全程序零拷贝或板端加速完成。单进程限一个 VINS 估计器；硬件数据源、长期运行、其他编码和板端缓存/带宽测量仍是后续门槛。

### 共享内存与 DMA-BUF 的补充评估（2026-10-10）

以下仍按一名熟悉 ROS/C++/Linux 的工程师估算，包含 A/B 和必要故障恢复验证；不能保证所有相机无改动接入。

| 范围 | 估算 | 通用边界 |
| --- | --- | --- |
| 现有只读视图 / 同进程组件 | 已完成基础链路 | 标准 Image 的 mono8/8UC1 与 owner 规则较通用；相机 SDK 到 Image 的复制尚未消除 |
| DDS 共享内存传输核验 | 2–5 工作日，含本机 RMW 服务问题排查；复杂情况另计 | 对标准消息较通用，但共享内存传输仍可能有序列化和复制，不等于零拷贝 |
| 真正跨进程共享像素 | 2–4 人周 | 通用缓冲池可复用，需双方支持共享帧协议/类型；普通 Image、bag、RViz 保留转换回退 |
| 一个已有 DMA-BUF 驱动的相机 → CPU/VINS | 1–2 人周 | 依赖该驱动支持导出/导入、CPU 可读布局、同步与缓冲归还 |
| 相机 → RGA → CPU/VINS，含跨进程句柄 | 2–4 人周，涵盖上一行基础，不简单相加 | 需协商格式、stride、fence、cache；换接口/驱动要新增适配器 |
| 驱动/封闭 SDK 不提供可共享缓冲 | 无统一工期承诺 | 可能只能在 SDK 输出后复制一次；不默认纳入内核驱动开发 |

建议保留统一的只读帧视图及 owner/归还规则，在数据源层分别接标准 ROS Image、普通共享内存和 DMA-BUF；算法层保持现有图像接口。普通共享内存的协议可与相机型号解耦，DMA-BUF 则以 Linux 驱动/SDK 能力为前提。进程间不能只发送指针或 fd 数字；共享内存用区域/偏移/代次标识，DMA-BUF 要传递实际句柄及元数据。先优先图像等大数据，不为小体积 IMU/GNSS 扩大基础设施。

本机 WSL 未暴露 DDR 控制器计数器和物理能量接口；CPU PMU 可用，但不能据此换算 DDR 搬运或功耗。后续实测需物理主机计数器或目标板接口/电源仪表，统一记录整个数据链与空闲背景，避免用仅 VINS 资源表推导整机能耗。具体核验与补充实验统一续写在 [对比报告](ROS1_ROS2_COMPARISON.md)。

### EuRoC 共享缓冲原型的范围

当前 ROS 2 分支提供独立数据源/VINS 的 memfd 共享像素与 VGEM DMA-BUF 后端，算法仍消费只读图像视图。共享内存协议采用有界池、代次及 owner 归还；设备句柄通过 SCM_RIGHTS 传递。EuRoC 源端仍复制一次像素，尚非相机 DMA → VINS 的全链路零拷贝。DDS、共享内存、DMA-BUF 共六轮完整单目/双目实验已归档在 [统一对比报告](ROS1_ROS2_COMPARISON.md)，各进程 CPU/PSS 分别记录。功能验证通过，不承诺收益：本机单目 memfd 没有 CPU 提升，VGEM 两模式 CPU 更高，双目还因背压未保持稳定 1 倍速；VGEM 只作桌面机制验证，普通 ROS 消息保持默认。

VGEM 只用于桌面真实内核句柄、映射及 CPU 同步验证；无相机/RGA硬件 DMA，不据此证明 ARM 的物理连续布局、fence、缓存行为或驱动通用性。通用灰度帧/owner 接口已落地，换相机仍需源端适配；Linux DMA heap 后端是未在本机验收的可选入口。板端工作量与原有通用性评估保持条件性，驱动稳定性与长期运行未因桌面原型而豁免。

历史基线/组件/PMU 已补 annotated tag；共享内存与 DMA-BUF 在各自数据验收、报告归档后分别打 tag。每个后续小目标沿用此规则，不移动已有 tag。源码切换后重建对应隔离环境；tag 及具体命令见 [ROS 2 环境说明](UBUNTU22_ROS2_SETUP.md#版本里程碑与切换)。

[1]: https://github.com/airockchip/librga/blob/main/docs/Rockchip_Developer_Guide_RGA_EN.md "Rockchip RGA 官方开发指南"
[2]: https://github.com/airockchip/librga/blob/main/docs/Rockchip_FAQ_RGA_EN.md "Rockchip RGA 官方 FAQ"
[3]: https://github.com/opencv/opencv/blob/4.x/modules/video/src/lkpyramid.cpp "OpenCV LK 官方源码"
[4]: https://github.com/ros2/design/blob/gh-pages/articles/intraprocess_communication.md "ROS 2 进程内通信设计"
[5]: https://github.com/ros2/ros2_documentation/blob/jazzy/source/How-To-Guides/Configure-ZeroCopy-loaned-messages.rst "ROS 2 Jazzy loaned message 官方文档源文件"
[6]: https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst "ROS 2 平台与生命周期 REP-2000"
[7]: https://github.com/zinuok/VINS-Fusion-ROS2 "社区参考 zinuok（Foxy）"
[8]: https://github.com/snktshrma/VINS-Fusion-ROS2 "社区参考 snktshrma（Humble/ARM）"
