# VINS-Fusion / x86 CPU 候选实验

核查日期：2026-10-10

## 方向与优先级

桌面上下一步优先补齐热点和逐帧延迟测量，再试 LK 金字塔/梯度复用、计算库线程预算及跟踪图开关，随后按热点决定缓冲复用或 SIMD。它们能在当前 x86 CPU 上验证，其中重复计算消除和所有权设计也能迁移到 ARM；收益幅度仍需在 RK3588 上实测

这是候选工作安排，不是新的实验结果。历史结果与原始数据保留在 [统一对比报告](05_EUROC_ROS1_ROS2_COMPARISON.md)，本页不改写既有结论。算法参照可沿用 `milestone-ros2-shared-memory-v1`（`9bd5cb2`），memfd、普通 ROS 和 VGEM 仍是同一代码中的可选后端

| 顺序 | 实验 | 初步工作量 | 收益预期与迁移价值 |
| --- | --- | --- | --- |
| 先做 | 热点、逐帧处理与排队计时 | 1–2 工作日 | 确认前端、后端、通信和校验的占比，为后续取舍提供依据 |
| 优先 | LK 金字塔与梯度复用 | 2–4 工作日 | 减少重复计算与中间分配；单目、双目均适用，ARM 可复用 |
| 优先 | OpenCV 线程预算对照 | 1–2 工作日 | 可能减少调度竞争和延迟波动；线程数需按目标硬件重新选择 |
| 优先 | 跟踪图开启/关闭对照 | 0.5–1 工作日 | 明确调试图生成与发布的成本；无显示的部署也可能受益 |
| 随热点 | 临时缓冲和容器复用 | 2–3 工作日 | 减少分配、释放及短时内存波动；需关注保留容量的内存代价 |
| 条件项 | SIMD 审计与有限热点试验 | 审计 1 工作日，原型另计 3–5 工作日 | x86 验证数据布局与向量化空间，不能直接预测 NEON 提速 |
| 条件项 | PoCL CPU 上的 OpenCL 原型 | 环境和有限算子 2–4 工作日，完整 LK 另估 | 提前验证 kernel 正确性、接口和同步；不能预测 Mali 性能 |

工期按一名熟悉本工程与 C++ 的工程师估算，包含局部验证和小规模完整回放，不包含长期稳定性、多序列验收或从零重写整个前端；各项逐个判断，不需要全部完成

## 优先实验的依据

**先定位成本**。现有 CPU 秒、RSS/PSS 和 PMU 表能够比较资源压力，尚不能说明哪段代码最值得优化。建议把前端分成时序 LK、双目 LK、补点和跟踪图，后端分开记录求解与边缘化；另记图像从入队到开始处理的等待，以及数据源、传输和逐帧 SHA256 的成本。计时用单调时钟、汇总后输出，避免逐帧打印改变负载；性能采样与正式 A/B 分开记录

函数调用栈可先评估 Linux perf 采样；工具可用性及 WSL 的具体采样能力需另行核验。Intel VTune 的 Hotspots 提供用户态采样与硬件事件采样，前者可在不安装采样驱动的条件下定位函数成本，实际 WSL 兼容性仍需验证。硬件计数器不可用时保留阶段计时即可，[Intel 官方说明](https://www.intel.com/content/www/us/en/docs/vtune-profiler/user-guide/2026-0/basic-hotspots-analysis.html)

**复用 LK 金字塔和梯度**。当前 [特征跟踪代码](../vins_estimator/src/featureTracker/feature_tracker.cpp) 直接把图像传给每次 `calcOpticalFlowPyrLK`，时序正反向与双目正反向会重复使用同一幅图。OpenCV 4.2 的 `buildOpticalFlowPyramid` 可预建金字塔与梯度，LK 可直接接收这些结果，因此可以先消除重复构建，再考虑重写计算内核，[OpenCV 4.2 接口](https://docs.opencv.org/4.2.0/dc/d6b/group__video__track.html)

建议按实际调用需要构建层级，在当前帧的多个 LK 调用之间复用，随后评估将当前左图结果保留为下一帧的上一左图。保持各调用原有层数、窗口、边界、梯度格式、终止条件及反向检查；预测失败时的更深层回退也必须保留。单目有预测时，预先构建所有深层可能浪费计算；因此复用收益需测，不能按 LK 调用次数直接换算加速比。缓冲不得在上一帧、反向跟踪或共享 owner 仍使用时覆盖

**控制计算库线程数**。OpenCV 4.2 的 LK 和梯度实现包含 `parallel_for_`；本机参照构建启用了 pthread 并行后端，未启用 TBB/OpenMP。可保持 VINS 的前后端线程模型，单独对照 OpenCV 默认线程数及 1、2、4 线程，先观察 CPU 秒、帧延迟尾部和上下文切换。Ceres 与 BLAS 的实际线程设置先记录，若要调整，另立实验；不能在同一轮同时改多个线程池，[OpenCV 4.2 源码](https://github.com/opencv/opencv/blob/4.2.0/modules/video/src/lkpyramid.cpp)、[线程控制接口](https://docs.opencv.org/4.2.0/db/de0/group__core__utils.html)

`setNumThreads` 是进程级设置，需要在开始计算前配置；同进程组件中会影响其他 OpenCV 用户。绑核可作为调度诊断，但 x86 的最优线程数和亲和性不能直接套到 RK3588 大小核

**测清跟踪图的成本**。当前 EuRoC 单目、双目配置均为 `show_track: 1`；[前端](../vins_estimator/src/featureTracker/feature_tracker.cpp) 会拼接图像、转彩色并绘制特征，[估计器入口](../vins_estimator/src/estimator/estimator.cpp) 会发布跟踪图，因此没有 RViz 不等于没有可视化成本。可只在实验配置副本中切换 `show_track`，保持特征数、`flow_back`、图像频率和求解器预算；标明这是部署输出配置变化，历史基线保留原值

**复用临时存储**。先由采样确定分配热点，再考虑 mask、LK 状态/误差数组、特征点 vector 及其他工作区的容量复用。`cv::Mat::create` 可在形状与类型匹配时复用存储，vector 可预留适量容量；数据内容仍须按原语义重置。跨帧共享的输入图像保持只读，不能把必要的输出、梯度或独立可写缓冲计作可删除的深拷贝；池化还可能提高常驻占用，需要同时看分配次数和 PSS

## 条件实验与统一边界

**SIMD 先审计再动手**。当前 OpenCV 构建缓存列出 SSE3 基线及 AVX2 等分派选项，但这不代表所有热点都运行 AVX2，4.2 的 LK 源码已有 `CV_SIMD128` 路径。先记录 `getBuildInformation`、`getCPUFeaturesLine` 和优化开关，再查看具体热点；只有存在明确空间时才做有限内核或编译配置对照。禁用优化可作诊断，不能拿它代替真实基线；显式 SSE/AVX 指令也不能原样移植为 NEON，[运行时查询](https://docs.opencv.org/4.2.0/db/de0/group__core__utils.html)、[OpenCV CPU 构建选项](https://github.com/opencv/opencv/wiki/CPU-optimizations-build-options)

**OpenCL 可验证功能**。PoCL 可以在 x86 CPU 上执行 OpenCL kernel，适合对照梯度、金字塔等有限算子的输出，验证 stride、边界、缓冲生命周期和同步。PoCL CPU 后端默认使用可用 CPU 线程，其开销与调度也要计入。它运行在本机 CPU 上，不能模拟 Mali 的缓存、吞吐、DMA-BUF 导入或功耗；是否迁移完整 LK，等 CPU 热点和局部原型结果再决定，[PoCL 官方使用说明](https://portablecl.org/docs/html/using.html)

现有 ROS 1 / ROS 2 参照 OpenCV 均关闭 OpenCL 和 IPP。新增运行时或 OpenCV 构建放入独立实验前缀，保留原版 OpenCV 4.2.0 / Ceres 1.14.0，不覆盖历史安装和二进制；uv 继续管理 Python 评估，原生 OpenCL/C++ 依赖单独锁定。纯 CPU 的金字塔复用与线程实验优先，OpenCL 环境作为后续独立目标

每个实验先做局部正确性和微基准，再做同模式完整 EuRoC A/B；每次只改变一个因素，串行运行，报告 CPU 秒、处理与排队延迟 p50/p95/p99、完整帧数、ATE/RPE、初始化/重置及内存占用。浮点和 SIMD 改动不能只检查图像接口，还要检查特征与轨迹。保留逐帧校验作为正式完整性依据，若另测关闭校验的生产配置，应单列结果并说明差异

现有 1 倍速完整回放能比较资源压力，最大吞吐需要另立加速供给实验并检查队列和末帧处理。WSL 未提供可用物理 DDR 与能量接口，仍不以 cache misses 或逻辑复制量替代。每个实现目标独立提交、验证后打 annotated tag，结果继续追加到第 05 份报告；本次只整理文档和候选方案，尚未实施上述优化
