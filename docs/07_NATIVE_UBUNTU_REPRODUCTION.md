# 原生 Ubuntu 复现清单

更新日期：2026-10-14

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
| `milestone-ros2-shared-repeats-v1` | 三传输 × 两模式 × 各五次，顺序轮换、冻结二进制与参数 | 30 | 已完成，`milestone-ros2-shared-repeats-native-ubuntu22-v1` |
| `milestone-ros2-desktop-handoff-v1` | 文档、入口、归档校验、分支重建及新主机交接 | 0 | 已完成，`milestone-ros2-desktop-handoff-native-ubuntu22-v1` |

合计 52 轮完整回放。除原版 ROS 1 已知清理 abort 外，正式 ROS 2 结果要求正常退出。失败立即停止当前批次，保存日志与已完成结果；修复后用新名称补跑，失败不混入成功统计

每阶段核验输入计数、初始化/重置、轨迹末帧、ATE/RPE、退出状态；共享路径另核验每帧像素/时间戳 SHA256、独立进程 fd 身份及零未归还槽位。ROS 1 未侵入原节点添加回调计数，其输入计数仅由 bag 核验，不能表述成消费端实收计数

CPU 报告全部线程累计秒，RSS/PSS 按进程分别记录。单进程 VINS 与同进程容器、双进程数据源的口径各自标明。回放与排空分开；目标 1 倍供给和排空后完整成功不能直接叫实时通过

每完成一个里程碑，先更新本机报告、冻结小型证据及新 SHA256，再单独提交并打新的 annotated tag。当前用户未授权远端 push，先保留本地分支与提交

## 本机权限与测量范围

初始 `kernel.perf_event_paranoid=4`，普通用户的 PMU 访问返回 EACCES。用户临时设为 2 后，task clock、cycles、cache misses 的访问探针通过；实验结束已核实恢复 4、临时 VGEM 已卸载，不写 sysctl 持久配置

用户加载 `vgem` 后，DRM 查询确认 `/dev/dri/card0` 的驱动为 `vgem`、版本 1.0.0，当前用户可读写。它是软件 DMA-BUF 机制验证，CPU 访问映射；没有使用 NVIDIA/AMD GPU 算法加速，也没有相机 DMA/RGA

未发现 DDR 控制器事件。CPU package/core 能量节点存在，但普通用户不可读；GPU hwmon 功率不代表 CPU VIO 功耗。因此 DDR 和 CPU 功耗暂记不可用，不用复制量、cache misses 或 GPU 读数代替

WSL 的 Cyclone DDS 小分片 XML 不直接视为本机必需配置。先核验本机默认配置，三路径对照采用统一、明确记录的配置；若参数不同，需要另列控制条件，不能混算收益

## 结果、版本与后台

统一结果为 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)。本机阶段证据在 `infra/desktop/comparison_reference/native_ubuntu22_20261013/`，30 次重复在 `infra/desktop/comparison_reference/native_shared_repeats_20261013/`；完整日志位于父目录 results，不覆盖历史目录

| 阶段 | 所属分支 commit | 本机事件目录（相对 `../results/ubuntu22-reproduction/`） |
| --- | --- | --- |
| ROS 1 四轮 | master `2731068`，日志审计修正 `8c7c8d2` | ros1-phase02、ros1-phase03 |
| ROS 2 重建及两轮参照 | ros2-humble `d198095` | ros2-bootstrap01、ros2-baseline01 |
| 八轮组件/owner | ros2-humble `d03feaf` | components01 |
| 两轮 PMU | ros2-humble `24fd362` | pmu01 |
| 四轮 ROS/memfd | ros2-humble `dd68d8d` | shared01 |
| 两轮 VGEM | ros2-humble `511f08f` | vgem01 |
| 30 次重复 | ros2-humble `13cfa87` | repeats01 |

各阶段由本机用户级临时 systemd unit 承接，不依赖工具 shell 存活，不安装持久服务或 timer。阶段终止时才向当前聊天排入一次通知，正常轮次不调用模型；hook 与聊天 ID 仅在忽略的 `.local-tests/`，不随 clone 迁移。正式执行器、采样和评估脚本均纳入 Git

ROS 1 执行器位于 master 的 `infra/desktop/scripts/run_native_ros1_reproduction.sh`；ROS 2 为 `run_native_ros2_phase.py`。控制台日志按唯一阶段目录隔离，结果名拒绝复用，补跑必须另立名称

## 局部检查与覆盖边界

图像适配器 ASan 三次通过，覆盖灰度 copy/share、owner、padded stride、颜色转换回退与非法布局拒绝。memfd/VGEM 各 1000 帧、4 槽位背压、上一帧 owner 保活、全像素校验和零未归还槽位通过；源码及重建步骤见 [局部探针归档](../infra/desktop/comparison_reference/native_ubuntu22_20261013/local_probes/)

Fast DDS/Cyclone DDS 两种 RMW 各六次单目/双目组件加载卸载通过，正确拒绝重复实例和非法配置，容器退出 0。本机未复现旧 WSL Fast DDS 组件服务故障；composed/split 仍使用统一 Cyclone DDS 控制条件

真实 EuRoC 单目/双目前十帧 copy/share 的特征 ID、相机编号、七维观测在 1e-12 容差内一致，见 [前端一致性归档](../infra/desktop/comparison_reference/native_ubuntu22_20261013/feature_consistency/)。没有 IMU 预测或全工程长期泄漏验收；ASan 只覆盖探针与共享协议源码，依赖未全插桩、泄漏检测关闭，子进程析构后 _exit

loop_fusion/global_fusion 仅验证启动及 SIGINT 退出 0，KITTI 两入口仅验证缺参退出 1，不当作回环、GNSS、KITTI 或 RViz 的数据验收。四个 package 的完整构建和依赖隔离核验通过，范围与完整 VIO 分开记录

## 30 次重复的固定条件与结论

批次 `native_shared_repeats_20261013` 完成于 2026-10-13 10:01:04–11:43:59 UTC，约 102.9 分钟。三路径 × 两模式 × 各五次，串行、模式/传输顺序轮换、间隔 10 秒，share 入口、1 倍目标供给、全帧 SHA256 校验，无回环/RViz

```bash
python3 infra/desktop/scripts/run_shared_repeats.py \
  --batch 新批次名 --repetitions 5 --cooldown 10 \
  --dds-profile infra/desktop/cyclonedds_native.xml --shared-device /dev/dri/card0
```

实验前工作树干净、无残留 VINS/播放器，复核原生环境；源码、实际 DDS XML、二进制及已加载 SDK 动态库共 353 个冻结文件未变。两端全输入、一次初始化、末帧、摘要/轨迹和退出通过，共享路径零错误、零池满等待、零未归还槽位；无失败轮次，CPU 采样增量与分布经独立复核

同轮对 ROS 的合计 CPU 变化中位数：memfd 双目 −0.05%、单目 +0.41%，没有明确省 CPU 收益；VGEM 双目 +163.33%、单目 +120.26%，增加主要在消费进程、具体操作归因未定位。共享源端 PSS 较低，完整 Q25/Q75/范围、每进程 RSS/PSS、回放/排空、ATE/RPE 见第 05 份报告

源端仍有一次像素复制，包含全帧校验成本；回放含启动/完成观察，排空含约 6 秒固定等待。完整处理和无池满等待不等于逐帧实时通过，不外推 RK3588 的缓存、DDR、功耗结果

## 失败与修正记录

最初 nohup 子进程在工具 shell 结束后消失，停于环境检查、未开始 VIO；中断证据在 `../results/ubuntu22-reproduction/ros1-phase01/`，不混入成功实验。改用用户级临时 systemd 服务后持续执行与通知均已验证

ROS 1 phase02 首轮成功，第二轮启动端口预检查出现 EADDRINUSE、无残留 ROS。补充 SO_REUSEADDR 并验证仍拒绝活跃监听者，余下三轮用 phase03 补跑；不改算法/回放条件，已成功结果不覆盖

phase03 曾复用控制台日志路径，导致 phase02 第二轮启动 stderr 被覆盖，旧冻结快照中的该日志为空。保留原清单，追加[注明聊天工具输出来源的 traceback 摘录](../infra/desktop/comparison_reference/native_ubuntu22_20261013/ros1_startup_failure_audit/)，不伪装成完整原始 stderr；四轮成功结果与哈希不受影响。正式执行器现按唯一阶段目录写日志，修正 commit 为 master `8c7c8d2`

前端局部探针首次编译缺 Ceres 头路径，失败日志保留；只补齐探针 CMake 依赖声明，未改 VINS。当前未使用的 codex/ubuntu22-ros1-reproduction 分支是最初误建入口，仍指向原 f85e0f1、无复现 commit；所有复现提交已回到所属原分支

## 最终交接核验

52 轮回放及局部探针全部验收，VINS C++、标定及算法参数未改。历史七份清单共 602 条、本机十一份清单共 706 条，合计实验归档 18 份/1308 条 SHA256 核验通过，另冻结交接证据 8 条；609 个历史快照 Git blob 与原 b250dc0 一致，八个历史 annotated tag 对象与远端一致，新 tag 不覆盖旧 tag

复核 ROS 2 实际动态库和构建路径隔离、Python/shell 语法、两份 bootstrap 的 ARM 拒绝路径及本地文档链接/锚点。文档整理没有重跑 VIO，已有完整重建和回放作为源码未变的验收依据

主机 PMU 已恢复为 4，临时 VGEM 已卸载，后台批次已结束；没有 VINS/播放器残留，不安装持久服务或 timer。核验证据见 [交接快照](../infra/desktop/comparison_reference/native_ubuntu22_20261013/handoff/)

```bash
python3 infra/desktop/scripts/verify_reproduction_archive.py
```

该脚本识别历史两种 SHA256 路径约定，校验所有新旧清单并比较原始 Git blob；默认只读，不依赖 `.local-tests/`。原生结果已替换当前文档中的 WSL 实测，历史证据及失败保持可追溯。后续板端工作需在 ROS 2 新目标分支建立 ARM 工具链、单独的工作区和一轮配置验收，不复制 x86 安装前缀；真实相机、RGA/NEON/NPU 不在本轮验收范围
