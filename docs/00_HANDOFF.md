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

实验室目标仍为灰度单目 + 200 Hz IMU、开环 VIO。EuRoC 源端仍向池中复制像素，VGEM 仅为软件 DMA-BUF/CPU 映射验证。RK3588、真实相机、RGA/NEON/NPU 未验收，回环/GNSS/KITTI/RViz 未完成数据验收；设计范围见 [第 01 份任务书](01_RK3588_DEPLOYMENT_PLAN.md)

下一项为用户已授权的 RK3588 板端工作：配置免密 SSH、固定 scp/部署/运行/日志回收工具、在联网主机下载依赖并优先交叉编译，再按配置各跑一轮。板端 Ubuntu 22.04.5/aarch64 已连通，尚未做板端 VIO 验收；已从 ROS 2 原生交接最新提交 7d42fac 建立目标分支，保留本轮分支/tag

板端工作入口为 [第 08 份文档](08_RK3588_WORKFLOW.md)，当前分支 codex/rk3588-ros2。免密 SSH、C++ scp/远端脚本/日志回收已验证，板端只读能力快照已保存；下一步本机 ARM 工具链、sysroot 与运行依赖重建，不把连接或 PMU 访问当作 VIO 验收

RK3588 的交叉 GCC 11.4.0、25 个工具链包与 807 个 ARM Humble sysroot 包已验收，ARM 小程序在板端运行通过；当前阶段继续固定版本视觉库、perf 和 VINS 构建，详见第 08 份文档。原 Docker 失败已归档并撤回，不混入成功结果
