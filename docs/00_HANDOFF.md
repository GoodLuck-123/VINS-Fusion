# 原生 Ubuntu 接手入口

更新日期：2026-10-13

当前在物理 Ubuntu 22.04.5 / Ryzen 7 9800X3D 主机复现已完成的 WSL 桌面实验，累计验收 22 轮完整回放；余下 30 次重复和最终交接核验。实测统一见 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)，清单、失败记录和批次方案见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)，重建/运行入口见 [第 04 份说明](04_UBUNTU22_ROS2_SETUP.md)

## 分支与里程碑

复现直接提交到所属原分支：ROS 1 为 master，ROS 2 为当前 checkout ros2-humble，从现有最新提交 `b250dc0` 继续。不另建复现分支，不将 ROS 2 合入 master，不移动历史 tag、不改写旧冻结归档；当前未授权远端 push

| 所属分支 / 阶段 | 本机验收 | 新 tag |
| --- | --- | --- |
| master / ROS 1 | 四轮，commit `2731068`；日志隔离及失败摘录说明修正 `8c7c8d2` | `baseline-ros1-native-ubuntu22-v1` |
| ros2-humble / 参照 | 两轮，commit `d198095`；隔离重建、动态库审计及全消息转换校验通过 | `baseline-ros2-native-ubuntu22-v1` |
| ros2-humble / 组件与 owner | 八轮，commit `d03feaf`；同模式轨迹字节一致，灰度 share 入口零物化 | `milestone-ros2-components-native-ubuntu22-v1` |
| ros2-humble / PMU | 两轮，commit `24fd362`；四类用户态事件可用、无复用 | `milestone-ros2-pmu-native-ubuntu22-v1` |
| ros2-humble / 共享内存 | 四轮，commit `dd68d8d`；ROS Image/memfd 摘要与轨迹一致、槽位全部归还 | `milestone-ros2-shared-memory-native-ubuntu22-v1` |
| ros2-humble / VGEM | 两轮；完整输入、DMA-BUF 注册、摘要/轨迹及退出/槽位归还通过 | `milestone-ros2-dmabuf-native-ubuntu22-v1` |
| ros2-humble / 30 次重复、最终交接 | 待完成，保持同一实现与控制条件 | 验收后新增 |

ROS 1 原版清理 abort 如实保留，算法、二进制及成功数据未改；ROS 1 输入计数由 bag 核验，不是节点实收计数。ROS 2 正式轮次均要求正常退出、完整消费和末帧覆盖。局部 ASan、owner/stride/回退、前端十帧一致性与两种 RMW 生命周期探针已通过，证据和覆盖边界见第 05/07 份文档

VGEM 在本机机制正确，但单轮双目/单目合计 CPU 为 440.87 / 244.58 秒，明显高于 ROS/memfd，主要增加在 VINS 消费进程，具体原因尚未定位。保持实现和全帧校验做五次重复，不将旧 WSL 收益或少量轮次当作本机稳定性能结论

## 继续执行

即将执行 `native_shared_repeats_20261013` 三路径 × 两模式 × 五次串行批次，统一 `infra/desktop/cyclonedds_native.xml` 原生默认配置与 `/dev/dri/card0` VGEM 节点。源码、实际 XML、二进制和已加载 SDK 动态库冻结，期间不编译/改脚本/切换分支；历史 WSL 小分片 XML 保留

用户级临时服务为 `vins-native-repeats01.service`，外层事件在 `../results/ubuntu22-reproduction/repeats01/`，批次状态/日志在 `../results/ros2/native_shared_repeats_20261013/`，预计约 104 分钟。只在完成或失败时向当前聊天通知一次，不在线模型轮询；hook 与聊天 ID 只在本机忽略的 `.local-tests/`，不安装持久服务或 timer

每阶段验收后独立提交并新增 annotated tag，失败结果保留且不混入成功统计。切换分支前确认服务结束且无 VINS/播放器残留；源码切换后重建，再在新 shell source 对应环境，已有 install 不代表当前源码

## 环境与边界

命令从仓库根执行，运行工作区是父目录；依赖、数据、完整日志分别在 `../.infra/`、`../data/`、`../results/`，根目录不建软链接。保留 OpenCV 4.2.0 / Ceres 1.14.0、原标定及算法参数，ROS shell 与 uv 评估 shell 分开

初始 PMU 权限值为 4，用户临时调为 2、加载 VGEM 后本机探针通过；实验结束恢复原 PMU 值。DDR 控制器事件未发现，CPU 能量节点普通用户不可读，二者记不可用，不用 cache misses、复制量或 GPU 功率替代

实验室目标仍为灰度单目 + 200 Hz IMU、开环 VIO。EuRoC 源端仍向池中复制像素，VGEM 仅为软件 DMA-BUF/CPU 映射验证。RK3588、真实相机、RGA/NEON/NPU 未验收，回环/GNSS/KITTI/RViz 未完成数据验收；设计范围见 [第 01 份任务书](01_RK3588_DEPLOYMENT_PLAN.md)
