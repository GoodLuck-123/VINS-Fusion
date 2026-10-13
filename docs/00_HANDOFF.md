# 原生 Ubuntu 接手入口

更新日期：2026-10-13

当前任务是在这台物理 Ubuntu 22.04.5 / Ryzen 7 9800X3D 主机复现所有已完成 WSL 桌面实验，完整清单见 [第 07 份文档](07_NATIVE_UBUNTU_REPRODUCTION.md)。当前 checkout 为 ros2-humble，复现提交直接落在所属原分支，不另建实验分支；历史 tag 和冻结归档不移动、不改写

ROS 1 四轮已完成，master 上里程碑 commit 为 `2731068`，新 tag 为 `baseline-ros1-native-ubuntu22-v1`；日志隔离和失败摘录说明修正为 `8c7c8d2`。算法、二进制及成功轮次数据未改，原版清理 abort 仍如实保留。详情见 [ROS 1 参照](03_EUROC_ROS1_BASELINE.md)及[统一报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

ROS 2 从现有最新提交 `b250dc0` 开始复现，隔离重建、动态库审计、全消息转换校验和局部 ASan/生命周期检查已通过；两轮完整双目 copy 参照已验收，状态/日志在 `../results/ubuntu22-reproduction/ros2-baseline01/`；新 tag 为 `baseline-ros2-native-ubuntu22-v1`。前端十帧 copy/share 特征一致性也已通过；八轮组件/owner 对照已完整验收，同模式轨迹字节一致，share 入口零物化；新 tag 为 `milestone-ros2-components-native-ubuntu22-v1`。两轮 PMU 已验收，新 tag 为 `milestone-ros2-pmu-native-ubuntu22-v1`；共享缓冲、VGEM 和 30 次重复实验仍待本机验收，不将旧 WSL 结论当作本机事实

先按 [第 04 份环境说明](04_UBUNTU22_ROS2_SETUP.md)了解入口，再按本次复现清单执行。第 04 份环境入口已更新为本机重建与局部核验状态；实际完整结果以第 05 份本机报告为准。设计范围见 [第 01 份任务书](01_RK3588_DEPLOYMENT_PLAN.md)，板端、真实相机、RGA/NEON/NPU 未验收

命令从仓库根目录执行，运行工作区是父目录；依赖、数据、完整日志放 `.infra/`、`data/`、`results/`，根目录不建软链接。保留 OpenCV 4.2.0 / Ceres 1.14.0，ROS shell 与 uv 评估 shell 分开。源码切换后重建，再 source 相应前缀，已有安装不代表当前源码

大批次由本机用户级临时 systemd 服务持续执行，只在阶段完成或失败时向当前聊天通知一次，不在线轮询。正式执行器纳入 Git，hook 与聊天 ID 只存在本机 `.local-tests/`。切换分支前确认服务结束且没有 VINS/播放器残留；失败结果保留并单独说明，不混入成功统计

每个里程碑验收后独立提交并新增 annotated tag。当前未授权远端 push；master 保留 ROS 1，ROS 2 的实现不合并进 master

PMU 两轮已完成，四类事件全部可用、运行占比为 1；继续共享像素、VGEM 和 30 次重复。已完成 16 轮正式回放，剩余阶段不使用旧 WSL 数值替代本机测量
