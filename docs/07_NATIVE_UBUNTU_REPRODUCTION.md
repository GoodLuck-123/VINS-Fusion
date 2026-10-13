# 原生 Ubuntu 复现清单

更新日期：2026-10-13

本轮在物理 Ubuntu 22.04 主机复现已完成的 WSL 实验，以本机结果替换当前文档中的实测结论。历史 tag、原始归档和 SHA256 清单保持原样，便于追溯；不复制旧安装前缀、通知 hook 或聊天 ID

## 主机与版本

Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，8 核 16 线程、约 30 GiB 内存。初始可用磁盘约 18 GiB；依赖、数据、完整日志分别位于仓库父目录的 `.infra/`、`data/`、`results/`

按用户要求，ROS 1 直接在 `master` 的最新提交 `f85e0f1` 上复现并提交，ROS 2 直接在 `ros2-humble` 最新提交 `b250dc0` 上继续；其他目标也使用所属分支，不另建复现分支。按当前代码的入口与参数复现每个里程碑所验收的行为，不将 ROS 2 分支合入 master，不移动历史 tag

保持 OpenCV 4.2.0、Ceres 1.14.0、EuRoC MH_01_easy 原输入、标定与算法参数。依赖按原 linux-64 锁重新安装，uv 按原锁重建评估工具。构建与实验串行，实验期间不编译，也不同时运行多个 VINS

## 验收顺序

| 历史里程碑 | 本机复现内容 | 完整回放数 | 状态 |
| --- | --- | ---: | --- |
| `baseline-ros1-euroc-v1` | 双目 IMU 两轮原版参照，加两轮 ROS 1/2 对照资源采样 | 4 | 已完成，`baseline-ros1-native-ubuntu22-v1` |
| `baseline-ros2-humble-v1` | 独立节点、双目 IMU、copy，保持迁移前入口；与 ROS 1 同口径对照 | 2 | 已完成，`baseline-ros2-native-ubuntu22-v1` |
| `milestone-ros2-components-v1` | 双目 standalone copy/share 各两轮、composed 各一轮；单目 standalone 各一轮；owner/stride/回退与组件生命周期检查 | 8 | 已完成，`milestone-ros2-components-native-ubuntu22-v1` |
| `milestone-ros2-pmu-v1` | 硬件能力探测、双目 copy/share 用户态 PMU 对照 | 2 | 已完成，`milestone-ros2-pmu-native-ubuntu22-v1` |
| `milestone-ros2-shared-memory-v1` | 单目/双目 split，ROS Image/memfd，各一轮；像素签名与槽位归还 | 4 | 已完成，`milestone-ros2-shared-memory-native-ubuntu22-v1` |
| `milestone-ros2-dmabuf-v1` | 单目/双目 split VGEM，与前一阶段同条件 ROS/memfd 对照 | 2 | 已完成，`milestone-ros2-dmabuf-native-ubuntu22-v1` |
| `milestone-ros2-shared-repeats-v1` | 三传输 × 两模式 × 各五次，顺序轮换、冻结二进制与参数 | 30 | 待执行 |
| `milestone-ros2-desktop-handoff-v1` | 文档、入口、归档校验、分支重建及新主机交接 | 0 | 待执行 |

合计 52 轮完整回放。除原版 ROS 1 已知清理 abort 外，正式 ROS 2 结果要求正常退出。失败立即停止当前批次，保存日志与已完成结果；修复后用新名称补跑，失败不混入成功统计

每阶段核验输入计数、初始化/重置、轨迹末帧、ATE/RPE、退出状态；共享路径另核验每帧像素/时间戳 SHA256、独立进程 fd 身份及零未归还槽位。ROS 1 未侵入原节点添加回调计数，其输入计数仅由 bag 核验，不能表述成消费端实收计数

CPU 报告全部线程累计秒，RSS/PSS 按进程分别记录。单进程 VINS 与同进程容器、双进程数据源的口径各自标明。回放与排空分开；目标 1 倍供给和排空后完整成功不能直接叫实时通过

每完成一个里程碑，先更新本机报告、冻结小型证据及新 SHA256，再单独提交并打新的 annotated tag。当前用户未授权远端 push，先保留本地分支与提交

## 本机权限与测量范围

初始 `kernel.perf_event_paranoid=4`，普通用户的 PMU 访问返回 EACCES。用户临时设为 2 后，task clock、cycles、cache misses 的访问探针通过；实验结束恢复 4，不写 sysctl 持久配置

用户加载 `vgem` 后，DRM 查询确认 `/dev/dri/card0` 的驱动为 `vgem`、版本 1.0.0，当前用户可读写。它是软件 DMA-BUF 机制验证，CPU 访问映射；没有使用 NVIDIA/AMD GPU 算法加速，也没有相机 DMA/RGA

未发现 DDR 控制器事件。CPU package/core 能量节点存在，但普通用户不可读；GPU hwmon 功率不代表 CPU VIO 功耗。因此 DDR 和 CPU 功耗暂记不可用，不用复制量、cache misses 或 GPU 读数代替

WSL 的 Cyclone DDS 小分片 XML 不直接视为本机必需配置。先核验本机默认配置，三路径对照采用统一、明确记录的配置；若参数不同，需要另列控制条件，不能混算收益

## 结果与通知

统一结果页为 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)，新增证据放在 `infra/desktop/comparison_reference/native_ubuntu22_20261013/`，30 次重复快照为 `infra/desktop/comparison_reference/native_shared_repeats_20261013/`，不覆盖旧目录

正式 ROS 1 入口为 `infra/desktop/scripts/run_native_ros1_reproduction.sh`。它依次完成四轮回放、独立 uv 评估和验收；每轮结果名不同，拒绝覆盖已有结果

批次在本地后台执行，完成或失败时向本机当前聊天排入一次处理请求；正常轮次不调用模型。hook 仅存在本机忽略的 `.local-tests/`，其失败单独记录，不能更改实验成功状态

本次后台由用户级临时 systemd unit `vins-native-ros1-phase02.service` 承接，不依赖工具 shell 持续存在，也不安装持久服务或定时任务。可通过 `systemctl --user status vins-native-ros1-phase02.service` 检查；各轮 VINS/rosbag PID 会变化，间隔和评估阶段可能暂时没有 VINS

首次使用 nohup 启动的子进程在工具 shell 结束后消失，停在环境核验，未开始 VIO；中断证据保留在 `../results/ubuntu22-reproduction/ros1-phase01/`，不计入成功实验。改用临时 systemd 服务后，已核验独立服务仍在运行、首轮 vins_node/rosbag 进程存在且轨迹日志持续产生

phase02 首轮回放与评估通过，第二轮在启动前的端口预检查返回 EADDRINUSE，无残留 ROS 进程。预检查补充 SO_REUSEADDR，与 ROS master 的地址复用行为一致；另核验仍拒绝活跃监听者，不改算法或回放条件。失败日志保留，不覆盖已成功的 `native_MH01_baseline_r01`

余下三轮由 `vins-native-ros1-phase03.service` 串行补跑，`run_native_ros1_reproduction.sh` 可接收显式补跑名称。当前服务检查命令为 `systemctl --user status vins-native-ros1-phase03.service`，阶段事件在 `../results/ubuntu22-reproduction/ros1-phase03/`

phase03 已完成并正常通知，四轮成功结果全部核验；VINS 二进制哈希一致，各有一次初始化、1831 个位姿、1819 个真值匹配，无重置/配对丢弃，末帧覆盖完整。回放正常结束，ROS 1 清理 abort 如实记录；主机无残留 ROS/VINS 进程及 master 监听。旧实验分支仅是本轮最初的误建入口，没有复现 commit，已将未提交改动转回 master

补跑日志审计：phase03 复用了原控制台日志路径，使 phase02 的第二轮启动 stderr 被覆盖；旧归档中的该日志为空，保留原冻结清单，不伪装成完整 stderr。失败事件仍在，当时读取到的 traceback 按聊天工具输出补充为[注明来源的摘录](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1_startup_failure_audit/)。四个成功轮次的轨迹、采样、验收和哈希不受影响

正式阶段执行器现将控制台日志放入每个唯一阶段目录的 trials 子目录，补跑不再复用前次日志。该修正只改变日志路径，不改回放、算法或二进制

ROS 1 里程碑 commit 为 master `2731068`，日志隔离与失败摘录审计修正为 `8c7c8d2`。后续 ROS 2 从现有 ros2-humble `b250dc0` 继续，当前 `vins-native-ros2-bootstrap01.service` 正在重新创建锁定依赖、构建并转换/校验 bag；没有并发 VIO 回放

ROS 2 从零重建、动态库隔离和全消息转换校验已通过。当前完整双目 copy 两轮由 `vins-native-ros2-baseline01.service` 执行，事件在 `../results/ubuntu22-reproduction/ros2-baseline01/`，逐轮状态在 `../results/ubuntu22-reproduction/native_ros2_baseline/`

本机局部探针已通过：图像适配器 ASan 连续三次；memfd/VGEM 各 1000 帧、4 槽位背压、上一帧 owner 保活、全像素摘要和零未归还槽位；两种 RMW 各六次单目/双目加载卸载，并正确拒绝重复实例与无效配置，容器正常退出。Fast DDS 在本机组件服务可用，未复现旧 WSL 的该服务故障；composed/split 仍按独立控制条件使用 Cyclone DDS。源代码、重建命令与证据见 [局部探针归档](../infra/desktop/comparison_reference/native_ubuntu22_20261013/local_probes/)

ASan 只覆盖测试可执行文件与共享协议源码，依赖未全插桩、泄漏检测关闭，子进程析构后 _exit；不代表全工程或长期泄漏验收

ROS 2 双目 copy 两轮验收完成，完整传感器计数、末帧、初始化和退出通过，精度与本机 ROS 1 参照一致。新 tag 为 baseline-ros2-native-ubuntu22-v1，直接提交于 ros2-humble；后续将运行真实 EuRoC 前端 copy/share 一致性探针及八轮组件/图像入口对照

ROS 2 参照里程碑已直接提交到 ros2-humble `d198095`，tag 为 baseline-ros2-native-ubuntu22-v1。单目/双目真实 EuRoC 前十帧 copy/share 特征 ID、相机编号和七维观测在 1e-12 容差内一致，证据见 [前端一致性归档](../infra/desktop/comparison_reference/native_ubuntu22_20261013/feature_consistency/)；局部探针首次编译缺 Ceres 头路径的错误已保留，只补齐探针依赖声明，未改 VINS 源码

八轮完整组件/owner 对照由 `vins-native-components01.service` 执行，阶段事件在 `../results/ubuntu22-reproduction/components01/`，逐轮冻结状态与日志在 `../results/ubuntu22-reproduction/native_components/`；预计约 27 分钟，成功或失败才通知一次，不在线模型轮询

八轮组件/owner 对照已完成，同模式轨迹逐字节一致，全部输入/末帧/退出通过；share 灰度入口物化为零，但少量重复没有稳定整机 CPU 提速结论。下一阶段为两轮双目 copy/share 用户态 PMU 对照

组件/owner 里程碑 commit 为 ros2-humble `d03feaf`。PMU 阶段由 `vins-native-pmu01.service` 串行运行两轮 copy/share，事件在 `../results/ubuntu22-reproduction/pmu01/`、逐轮状态在 `../results/ubuntu22-reproduction/native_pmu/`。能力复核仍为物理主机、权限值 2、CPU PMU 可用；DDR 及 CPU 功耗不可用。仅将报告中的 Virtualized CPU PMU 描述改为通用 CPU PMU diagnostics，未改计数逻辑

PMU 两轮已验收，四类用户态 CPU 事件均可用且无复用，完整输入、初始化、末帧和退出通过，同模式轨迹字节一致。资源采样 CPU 为 copy 162.16 秒、share 162.93 秒，不将单轮差异写成稳定收益；本阶段累计完成 16 轮正式回放，证据与测量范围见第 05 份报告

PMU 里程碑 commit 为 ros2-humble `24fd362`，tag 为 `milestone-ros2-pmu-native-ubuntu22-v1`。共享像素四轮计划由 `vins-native-shared01.service` 执行，事件在 `../results/ubuntu22-reproduction/shared01/`，逐轮状态在 `../results/ubuntu22-reproduction/native_shared/`；原生默认 Cyclone DDS XML 在本阶段及后续 VGEM/重复实验统一使用、冻结并归档。执行器只补充实际 XML 冻结与配置/设备参数，记录重复阶段排空时间，不改算法

共享传输四轮已验收：原生 DDS 默认配置通过；同模式输入摘要与轨迹字节一致，全部计数/末帧/初始化/退出通过，memfd 零错误、零未归还、零池满等待。源端仍向池中复制一次，不声明全链路零拷贝；本轮累计完成 20 轮，后续保持相同二进制、配置和校验条件运行 VGEM 两轮

共享内存里程碑 commit 为 ros2-humble `dd68d8d`，tag 为 `milestone-ros2-shared-memory-native-ubuntu22-v1`。VGEM 两轮计划由 `vins-native-vgem01.service` 执行，事件在 `../results/ubuntu22-reproduction/vgem01/`、逐轮状态在 `../results/ubuntu22-reproduction/native_vgem/`。不改 VINS C++，仅将传输改为 vgem；沿用前阶段原生默认 DDS XML 和 SHA256 校验

VGEM 两轮已验收，三路径同模式输入摘要与轨迹完全一致，DMA-BUF 注册、完整计数/末帧/初始化/退出及零未归还槽位通过。CPU 合计双目 440.87 秒、单目 244.58 秒，明显高于此前 ROS/memfd，主要增加在 VINS 消费进程；原始采样增量核验一致，具体原因未定位。本阶段累计完成 22 轮，不改实现或关闭校验来追求收益

## 30 次重复的冻结方案

三路径单轮均已验收。批次名为 `native_shared_repeats_20261013`，单目/双目各 ROS Image、memfd、VGEM 五次，共 30 次；各轮串行，模式及传输顺序轮换，间隔 10 秒。沿用同一二进制、标定/算法参数、share 入口、1 倍目标供给和全帧 SHA256 校验，显式指定原生默认 XML 与已核验的 VGEM 节点

```bash
python3 infra/desktop/scripts/run_shared_repeats.py \
  --batch native_shared_repeats_20261013 --repetitions 5 --cooldown 10 \
  --dds-profile infra/desktop/cyclonedds_native.xml --shared-device /dev/dri/card0
```

启动前工作树须干净、无活动 VINS/播放器，复核原生环境，冻结源码、实际 DDS XML、VINS/数据源二进制和已加载 SDK 动态库。失败立即停止并保留已完成结果，失败不混入统计；期间不编译、改脚本或切换分支。统计包括中位数/四分位/范围、同轮 ROS 对照 CPU 变化、各进程 RSS/PSS、回放/排空、等待计数及 ATE/RPE，不把独立峰值相加当作同时峰值

本机用户级临时服务名为 `vins-native-repeats01.service`，外层事件在 `../results/ubuntu22-reproduction/repeats01/`，批次状态/日志/统计在 `../results/ros2/native_shared_repeats_20261013/`。预计约 104 分钟，只在完成或失败时由外层 hook 通知当前聊天一次，批次内部不另发通知，不在线模型轮询
