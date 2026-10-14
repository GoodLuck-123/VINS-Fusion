# 原生 Ubuntu 接手入口

更新日期：2026-10-14

当前在物理 Ubuntu 22.04.5 / Ryzen 7 9800X3D 主机复现已完成的 WSL 桌面实验，累计验收全部 52 轮完整回放；最终交接核验已完成。实测统一见 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)，清单、失败记录和批次方案见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)，重建/运行入口见 [第 04 份说明](04_UBUNTU22_ROS2_SETUP.md)

## 分支与里程碑

复现直接提交到所属原分支：ROS 1 为 master，桌面 ROS 2 为 ros2-humble，从现有最新提交 `b250dc0` 继续。不另建复现分支，不将 ROS 2 合入 master，不移动历史 tag、不改写旧冻结归档；当前未授权远端 push

| 所属分支 / 阶段 | 本机验收 | 新 tag |
| --- | --- | --- |
| master / ROS 1 | 四轮，commit `2731068`；日志隔离及失败摘录说明修正 `8c7c8d2` | `baseline-ros1-native-ubuntu22-v1` |
| ros2-humble / 参照 | 两轮，commit `d198095`；隔离重建、动态库审计及全消息转换校验通过 | `baseline-ros2-native-ubuntu22-v1` |
| ros2-humble / 组件与 owner | 八轮，commit `d03feaf`；同模式轨迹字节一致，灰度 share 入口零物化 | `milestone-ros2-components-native-ubuntu22-v1` |
| ros2-humble / PMU | 两轮，commit `24fd362`；四类用户态事件可用、无复用 | `milestone-ros2-pmu-native-ubuntu22-v1` |
| ros2-humble / 共享内存 | 四轮，commit `dd68d8d`；ROS Image/memfd 摘要与轨迹一致、槽位全部归还 | `milestone-ros2-shared-memory-native-ubuntu22-v1` |
| ros2-humble / VGEM | 两轮，commit `511f08f`；完整输入、DMA-BUF 注册、摘要/轨迹及退出/槽位归还通过 | `milestone-ros2-dmabuf-native-ubuntu22-v1` |
| ros2-humble / 30 次重复 | commit `13cfa87`，已完成，三路径 × 两模式 × 各五次，完整输入、轨迹和槽位归还通过 | `milestone-ros2-shared-repeats-native-ubuntu22-v1` |
| ros2-humble / 最终交接 | 历史/本机归档、隔离环境和文档入口核验完成 | `milestone-ros2-desktop-handoff-native-ubuntu22-v1` |

ROS 1 原版清理 abort 如实保留，算法、二进制及成功数据未改；ROS 1 输入计数由 bag 核验，不是节点实收计数。ROS 2 正式轮次均要求正常退出、完整消费和末帧覆盖。局部 ASan、owner/stride/回退、前端十帧一致性与两种 RMW 生命周期探针已通过，证据和覆盖边界见第 05/07 份文档

五次重复的本机结论：memfd 相对 ROS 的合计 CPU 变化中位数为双目 −0.05%、单目 +0.41%，没有明确省 CPU 收益；VGEM 为 +163.33% / +120.26%，增加主要在 VINS 消费端，具体原因未定位。共享路径源端 PSS 较低，具体范围与测量口径见第 05 份报告，不沿用旧 WSL 收益

## 交接核验

`native_shared_repeats_20261013` 已完成，统一原生默认 DDS XML 与 VGEM 节点，353 个冻结文件未变。临时服务 `vins-native-repeats01.service` 已结束且没有 VINS/播放器残留；外层事件在 `../results/ubuntu22-reproduction/repeats01/`，状态/日志在 `../results/ros2/native_shared_repeats_20261013/`

实验归档 18 份/1308 条 SHA256 已通过，另有交接快照 8 条，609 个旧快照 blob 未变、八个原 tag 与远端一致；隔离环境、文档入口及脚本检查通过，PMU 已恢复 4、临时 VGEM 已卸载。完成通知只在阶段终止时触发一次，hook 与聊天 ID 不迁移，不安装持久服务或 timer

每阶段验收后独立提交并新增 annotated tag，失败结果保留且不混入成功统计。切换分支前确认服务结束且无 VINS/播放器残留；源码切换后重建，再在新 shell source 对应环境，已有 install 不代表当前源码

## 环境与边界

命令从仓库根执行，运行工作区是父目录；安装前缀、数据、完整日志分别在 `../.infra/`、`../data/`、`../results/`，根目录不建软链接。按用户新增要求，交叉编译依赖源码/缓存/sysroot 在仓库 `dependencies/` 下保留占位目录，下载内容忽略；clone 后用一个命令补齐，见 [第 09 份说明](09_DEPENDENCIES.md)。旧桌面环境和冻结 SDK 保持原位。保留 OpenCV 4.2.0 / Ceres 1.14.0、原标定及算法参数，ROS shell 与 uv 评估 shell 分开

初始 PMU 权限值为 4，用户临时调为 2、加载 VGEM 后本机探针通过；实验结束已恢复原 PMU 值 4、卸载临时 VGEM。DDR 控制器事件未发现，CPU 能量节点普通用户不可读，二者记不可用，不用 cache misses、复制量或 GPU 功率替代

实验室目标仍为灰度单目 + 200 Hz IMU、开环 VIO。EuRoC 源端仍向池中复制像素，VGEM 仅为软件 DMA-BUF/CPU 映射验证。RK3588 双目基线、单目和组件/owner 已通过，ROS Image/memfd 共享完整对照已通过，完整 DMA heap 已通过；真实相机、RGA/自研 NEON/NPU、回环/GNSS/KITTI/RViz 未完成数据验收；设计范围见 [第 01 份任务书](01_RK3588_DEPLOYMENT_PLAN.md)

## RK3588 当前状态

本轮板端任务已完成：免密 SSH、固定 scp/远端执行/日志回收、主机交叉编译、统一依赖下载、板端 profile 与每个去重配置一轮实验。合计 15 次实际完整回放，ROS 2 14 个配置、ROS 1 唯一双目配置一个；没有重启桌面重复/神经网络批次，没有远端 push

| 目标 / 验收 | 所属分支与里程碑 |
| --- | --- |
| ROS 2 交叉构建与运行环境 | codex/rk3588-ros2，构建 tag milestone-rk3588-ros2-cross-build-v1，运行环境 55fdcd8 / milestone-rk3588-ros2-runtime-v1 |
| Fast DDS addon / 完整双目参照 | a29ee44 / milestone-rk3588-fastrtps-runtime-v1；76d40f8 / baseline-rk3588-ros2-v1 |
| 单目/组件/owner / PMU | a545a95 / milestone-rk3588-components-v1；af6c635 / milestone-rk3588-pmu-v1 |
| 共享计算探针 / 四轮 ROS-memfd | 8f04c3f / milestone-rk3588-shared-probe-v1；5e685b1 / milestone-rk3588-shared-memory-v1 |
| 实际 system DMA heap 两轮 | 4213e2a / milestone-rk3588-dmabuf-v1 |
| ROS 1 依赖 / 构建 / 视觉库计算 | codex/rk3588-ros1，从 master 最新 8c7c8d2 独立建立；30b9d96、30790b0、6c4703a，对应 dependencies / cross-build / legacy-libs tag |
| ROS 1 运行环境 / 一轮完整参照 | 92b1bbb / milestone-rk3588-ros1-runtime-v1；2d76d3a / baseline-rk3588-ros1-v1 |

统一指标在 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)。ROS 1 ATE/RPE 为 0.260330 / 0.00312228 m，VINS CPU 690.02 s；ROS 2 双目 standalone/copy 为 0.269229 / 0.00313946 m、673.68 s。编译器、SuiteSparse/Boost/BLAS、RMW 和回放/采样口径不同，一轮不证明 ROS 版本带来提速/精度变化

ROS 2 正式轮次退出均为 0、完整实收/末帧/摘要/归还通过；ROS 1 input counts 是 bag records，未新增节点实收计数，原同步线程清理 abort −6 与桌面原版一致，如实保留，不称正常退出。ROS 1 外层阶段在已回收日志后的主机评估参数错误处失败，后续只恢复评估，没有第二次回放；原失败事件/日志未改写。对应旧通知按路径/SHA256 去重，见 [第 10 份账本](10_PHASE_EVENT_AUDIT.md)

当前目标 firefly@10.106.0.220，RK3588S/Ubuntu 22.04.5/内核 5.10.110；板端保持离线，下载/编译在联网主机。OpenCV 4.2.0/Ceres 1.14.0/Eigen 3.3.9 和原算法/标定保持不变，板端 CPU perf 计数/采样探针及实际 VINS PMU 已通过，权限保持板端原值 2。私有 Noetic/Python 3.8 保留系统 Python 3.10 与 glibc/loader，不复制 x86 install 代替重建

| 当前有效产物 | 位置 |
| --- | --- |
| 主机远端工具 | ../.infra/bin/vins-remote，两目标分支均有相同源码可重建 |
| ROS 2 主机库/项目 | ../.infra/rk3588/legacy/、ros2_ws_overlay/install/ |
| ROS 1 主机库/项目 | ../.infra/rk3588/ros1-legacy/、ros1_ws/devel/；GeographicLib 在其 build/global_fusion/ThirdParty/GeographicLib/ |
| ROS 2 板端运行包 | /home/firefly/vins-workspace/jobs/1791960441164-99946/ros2-payload |
| ROS 1 板端运行包 | /home/firefly/vins-workspace/jobs/1791970072506-133971/ros1-payload02 |
| 独立 ROS 1 checkout | /home/eric/projects/VINS-Fusion-rk3588-ros1 |

旧混链前缀、缺启动器的首次运行包与失败证据保留，只作追溯，不继续作为部署输入。固定工作流见 [第 08 份说明](08_RK3588_WORKFLOW.md)，clone 后一次下载见 [第 09 份说明](09_DEPENDENCIES.md)；数据和完整日志留父工作区，源码仓库/历史 tag 不覆盖

结束审计无旧板端作业活进程。桌面 VGEM 是软件 DMA-BUF 机制验证，板端实测是 /dev/dma_heap/system/backend=2；源端仍复制像素到池，没有真实相机/RGA/GPU fence 或端到端零拷贝证据。排空成功不是实时性验收，DDR 带宽/功耗不可用；真实相机、RGA/自研 NEON/NPU、回环/GNSS/KITTI/RViz 仍无完整数据验收

板端墙上时钟未同步，主机事件 UTC 与单调时钟用于阶段/资源时间。历史统一账本不改写，新增阶段续写；两分支的 core/config 保持各自桌面参照，必要失败和恢复均可追溯
