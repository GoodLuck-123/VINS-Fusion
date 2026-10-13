# 原生 Ubuntu 22.04 / ROS 2 Humble

更新日期：2026-10-13

先读 [交接入口](00_HANDOFF.md)和[复现清单](07_NATIVE_UBUNTU_REPRODUCTION.md)。本页命令针对当前物理 Ubuntu 22.04.5 x86_64 主机；锁定依赖、四个 package 和数据转换已从零重建，实际动态库隔离核验通过。本机各里程碑累计 52 轮完整 VIO 已验收，最终交接核验继续，结果统一写 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

## 分支与固定依赖

ROS 1 直接在 master 提交，ROS 2 直接在 ros2-humble 最新提交继续。每次切换先处理工作树，确认没有实验服务运行，再重建并在新 shell source 对应前缀；已有 install 不代表当前源码

| 项目 | ROS 1 | ROS 2 |
| --- | --- | --- |
| ROS | Noetic | Humble |
| OpenCV / Ceres / Eigen | 4.2.0 / 1.14.0 / 3.3.9 | 相同版本 |
| cv_bridge | 1.16.2 | 3.2.1，同 OpenCV 源码重建 |
| ROS 前缀 | `../.infra/ros1` | `../.infra/ros2` |
| OpenCV / Ceres 前缀 | `../.infra/legacy` | `../.infra/legacy_ros2` |
| 工作区 | `../.infra/vins_ws`、`bridge_ws` | `../.infra/ros2_ws` |

ROS/C++ 按 `ros2-linux-64.lock` 创建，评估按同一 `uv.lock` 管理，不叠加系统 `/opt/ros`、系统 OpenCV 或 ROS 1 前缀。原生锁只支持 Linux x86_64，不在 ARM 使用，不复制旧安装前缀

保持算法、标定、特征配置、反向光流、隔帧后端入队、3 ms 双目配对和求解器时间预算。普通 ROS Image 为默认传输，copy 保留原图像深拷贝入口，share 保留只读视图和 owner；不要用丢帧、减速或修改参数制造收益

## 重建与核验

从仓库根目录执行：

```bash
git switch ros2-humble
VINS_BUILD_JOBS=4 bash infra/desktop/scripts/bootstrap_ros2.sh
```

已有环境时增量构建用 `build_ros2.sh`，原生库重建用 `build_ros2_native.sh`。在新的 ROS 2 shell 中：

```bash
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/verify_ros2_environment.py
```

本机 ldd 与 compile_commands 核验通过：OpenCV/Ceres/cv_bridge 来自 ROS 2 专用前缀，未混入 ROS 1 或系统视觉库。四个 package 编译成功不等于回环、GNSS、KITTI、RViz 已完成数据验收

## 数据与一轮实验

转换入口为 `convert_euroc_ros2.sh`。本机已逐消息比较所有图像像素、IMU 字段/协方差、frame ID、header 时间与 bag 记录时间；ROS 1 Header.seq 在 ROS 2 中不存在，除此以外共同传感器字段摘要一致。左右图各 3682 帧，IMU 36820 条，证据为 `../results/ros2/bag_conversion.json`

在 ROS 2 shell 运行双目 copy 参照：

```bash
python infra/desktop/scripts/run_ros2_euroc.py --name 新名称   --mode stereo_imu --deployment standalone --image-mode copy --image-transport ros --rate 1
```

单目将 mode 改为 mono_imu；share 图像入口将 image-mode 改为 share。每次使用新名字，拒绝覆盖已有结果。实验配置只修改输出路径，保持原标定与算法参数；按原始时间戳完整回放后等待后端排空，再单列退出状态

在独立普通 shell 评估：

```bash
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python   infra/desktop/scripts/evaluate_baseline.py ../results/ros2/新名称
```

采用 evo、IMU/body 真值、SE(3) 对齐、不校正尺度、0.01 秒最大匹配差；RPE 为相邻位姿间隔。ROS Python 与 uv venv 不在同一 shell 叠加

## 组件、owner 和传输入口

| deployment | VINS 与数据源 |
| --- | --- |
| standalone | 独立 VINS + 外部 ros2 bag |
| component | 容器内 VINS + 外部 ros2 bag |
| composed | 同一容器内 EuRoC 源 + VINS |
| split | 独立 C++ EuRoC 源 + VINS |

同进程组件需双方启用进程内通信；外部 bag 仍经过跨进程边界。当前 upstream 全局状态限制一个进程仅一个 VINS，重复实例应拒绝；卸载后应停止线程、释放发布器及 owner，支持再加载。完整生命周期和本机 RMW 服务行为按复现清单重新检查

share 对原生 mono8/8UC1 使用只读视图，上一左图 owner 保留到下一次跟踪返回。颜色转换、字节序不匹配允许物化，长期关键帧和 OpenCV 计算产物仍有必要输出；不能称为全程序零拷贝

split 可选择 `--image-transport ros/memfd/vgem/dma_heap`，共享后端要求 share。memfd 是普通共享像素，VGEM 导出真实 DMA-BUF，通过 SCM_RIGHTS 注册 fd、逐帧发送元数据，32 槽位有代次/归还协议。EuRoC 解包后仍复制一次到池中，不是相机全链路零拷贝；不支持热重连或多消费者

本机用户已加载 VGEM，DRM 查询确认 `/dev/dri/card0` 驱动名 vgem 且可读写，不对真实 GPU 节点尝试分配。VGEM 是 CPU 映射的软件分配器，没有相机 DMA、RGA 或 GPU 算法加速；DMA heap 本机仍待验证

组件/composed/split 对照使用已锁定的 Cyclone DDS。本机四轮 split ROS Image/memfd 已通过，采用 `cyclonedds_native.xml` 明确保留原生默认值；VGEM 两轮已使用相同 XML，已完成的 30 次重复也统一并冻结实际文件。历史 `cyclonedds_wsl.xml` 保留，不把旧 WSL 网络故障当成本机原因，不与不同配置混算收益

## 正式阶段与后台

`run_native_ros2_phase.py --phase baseline/components/pmu/shared/vgem --prefix 唯一名称` 串行执行预定完整轮次，自动评估、验收，冻结源码与本机二进制。`--dry-run` 查看方案，split 可用 `--dds-profile` 明确指定配置；不同阶段使用不同 prefix，失败立即停止，补跑另立名称，不覆盖前次证据

本机后台由用户级临时 systemd unit 承接 `run_local_phase.py`，不安装持久服务或 timer。事件/state 与逐轮日志留在唯一阶段目录；完成或失败才通知当前聊天一次。不要在线模型轮询，不迁移旧机器 hook 或聊天 ID；临时 probe 源码需可重建，不能当作已跟踪依赖

30 次重复实验使用现有 `run_shared_repeats.py`，先完成单轮三路径验收并提交冻结方案，再运行；每模式每传输各五次，顺序轮换，期间不编译/切换源码。本机显式指定 `--dds-profile infra/desktop/cyclonedds_native.xml --shared-device /dev/dri/card0`；默认参数仍保留历史配置，实际 XML/设备写入状态，不把桌面入口直接当板端入口

## 指标、权限和版本

报告进程全线程累计 CPU 秒、每进程 RSS/PSS、回放和排空时间、完整输入计数、末帧、初始化/重置、ATE/RPE及退出。共享路径另核验全帧像素/时间戳签名、fd 身份和零未归还槽位。独立峰值不能相加当作同时峰值；目标倍率 1 和排空成功不等于实时通过

初始 PMU 权限值为 4，用户临时设置 `kernel.perf_event_paranoid=2` 后 CPU 事件探针通过。PMU 对照加 `--perf-counters`，记录全部继承线程的用户态事件、time_enabled/time_running 和错误；不自动换算 DDR，实验结束恢复原权限值

本机未发现 DDR 控制器事件，CPU 能量节点普通用户不可读，GPU 功率不代表 CPU VIO 功耗；相关值记不可用，不用 cache misses、复制量或 CPU 占用代替

历史 tag 原样保留，新验收 tag 以 native Ubuntu 命名；每个里程碑直接提交到所属分支，不自动 push。列表及状态见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)

本机局部探针已通过：图像适配器 ASan 连续三次；memfd/VGEM 各 1000 帧、4 槽位背压、上一帧 owner 保活、全像素摘要和零未归还槽位；两种 RMW 各六次单目/双目加载卸载，并正确拒绝重复实例与无效配置，容器正常退出。Fast DDS 在本机组件服务可用，未复现旧 WSL 的该服务故障；composed/split 仍按独立控制条件使用 Cyclone DDS。源代码、重建命令与证据见 [局部探针归档](../infra/desktop/comparison_reference/native_ubuntu22_20261013/local_probes/)

ASan 只覆盖测试可执行文件与共享协议源码，依赖未全插桩、泄漏检测关闭，子进程析构后 _exit；不代表全工程或长期泄漏验收

扩展入口冒烟通过：loop_fusion_node、global_fusion_node 启动存活并 SIGINT 退出 0，两个 KITTI 入口缺少参数时退出 1；VINS 启动/退出由两轮完整回放验证。源码和记录见本机 ROS 2 参照快照的 entrypoints_smoke 子目录，仅接口检查，不等于回环/GNSS/KITTI 数据验收

VGEM 两轮完整输入、摘要/轨迹、DMA-BUF 身份与槽位归还已通过，但本机消费进程 CPU 代价明显增加。机制正确性与性能分开判断；已完成的 30 次重复保持同一实现、配置和全像素校验，具体本机观测见第 05 份报告

30 次重复已验收：memfd 同轮合计 CPU 变化中位数双目 −0.05%、单目 +0.41%，VGEM 为 +163.33% / +120.26%。三路径全输入、轨迹/摘要和退出通过，共享槽位全部归还且无池满等待；共享源端 PSS 较低。完整统计与测量窗口见第 05 份报告，不沿用旧 WSL 收益
