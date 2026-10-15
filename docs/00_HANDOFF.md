# ROS 1 接手与完成状态

更新日期：2026-10-14

本分支 codex/rk3588-ros1 从 ROS 1 master 最新 8c7c8d2 独立建立，已完成 RK3588 主机交叉构建、离线运行环境和唯一双目配置一轮回放/评估。原 master、桌面 ros2-humble、板端 codex/rk3588-ros2 与历史 tag 保留，未合并 ROS 2 核心；2026-10-14 用户已授权核验后 push 所属分支和新增 tag

## 桌面与板端里程碑

原生 Ubuntu 桌面 ROS 1 四轮已在 master 验收，tag baseline-ros1-native-ubuntu22-v1，原清理 abort 单列。原生 Ubuntu 全部 52 轮总体记录在所属 ros2-humble；本分支的历史冻结数据保持原样，实测统一写 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

| ROS 1 板端目标 | 验收提交 / annotated tag |
| --- | --- |
| 锁定依赖下载与离线复核 | 30b9d96 / milestone-rk3588-ros1-dependencies-v1 |
| 五包/六程序/70 个 ARM ELF 构建闭包 | 30790b0 / milestone-rk3588-ros1-cross-build-v1 |
| 固定视觉库实际 RK3588 GFTT/LK/两种稀疏求解 | 6c4703a / milestone-rk3588-ros1-legacy-libs-v1 |
| 私有 Noetic/Python 3.8、4210 文件/导入/动态库/订阅就绪 | 92b1bbb / milestone-rk3588-ros1-runtime-v1 |
| 唯一双目配置一轮完整回放和主机评估 | 2d76d3a / baseline-rk3588-ros1-v1 |

ROS 1 bag 左右图各 3682、IMU 36820，1831 姿态/1819 匹配、末帧覆盖、一次初始化、无重置/配对丢帧。ATE/RPE 为 0.260330 / 0.00312228 m，VINS 全线程 CPU 690.02 s，RSS/PSS 峰值 61.55/55.21 MiB，回放/排空 189.59/6.10 s；源端资源、DDR/功耗不可用，不当作合计 CPU 或实时性验收

输入计数是 bag records，未新增原节点实收计数；ROS master/rosbag 退出 0，原未 join 同步线程的 VINS 清理 abort −6 与桌面一致，明确保留，不称正常退出。外层 ros1-baseline01 因日志已收回后的主机评估参数错误失败，ros1-evaluation01 仅补评估并通过，没有第二次回放；失败事件/日志不改写。完整证据见 infra/rk3588/reference/ros1_baseline_20261014/

## 有效环境与固定入口

目标 firefly@10.106.0.220，RK3588S/Ubuntu 22.04.5/厂商内核 5.10.110；板端离线，下载/编译在联网主机。独立 Focal/Noetic/GCC9.4 保持 OpenCV 4.2.0/Ceres 1.14.0/Eigen 3.3.9 和原算法/标定；不在 ARM 跑 x86 bootstrap，不传 x86 install 代替重建，不替换板端 glibc/loader/系统 Python 3.10

| 有效产物 | 位置 |
| --- | --- |
| 交叉依赖空目录与下载入口 | dependencies/，python3 infra/dependencies/fetch.py，见第 09 份文档 |
| 视觉库 / 项目构建 | ../.infra/rk3588/ros1-legacy/、ros1_ws/devel/ |
| 主机运行包 | ../.infra/rk3588/ros1-payload02/；首次缺 rosversion 的 ros1-payload 仅追溯 |
| 已部署运行包 | /home/firefly/vins-workspace/jobs/1791970072506-133971/ros1-payload02 |
| 本分支 checkout | /home/eric/projects/VINS-Fusion-rk3588-ros1 |
| 同源码 C++ 远端工具 | infra/remote/，../.infra/bin/vins-remote |

编译器/ARM binutils 主机库隔离，SDK 绝对链接与 Python/原生 CMake 导出重定位可重做；失败证据保留。cv_bridge C++ 下载源码不变，构建副本只关闭可选 Python 扩展，不提供目标 Python cv_bridge。C++ 算法/core/config 与 master 8c7c8d2 一致；运行包旧来源字段的 tag 对象与剥离提交对应关系在第 05 份报告说明，冻结包/哈希不改

工作流见 [第 08 份说明](08_RK3588_WORKFLOW.md)，统一下载见 [第 09 份说明](09_DEPENDENCIES.md)。run_ros1_board_phase.py 一次调用完成传 bag/核验/原回放/回收/主机评估，--evaluate-only 只恢复既有轨迹的主机评估；默认核对已接受归档的文件清单。ROS/C++ 与 uv shell 分开，每次源码改变先重建，每次结果用新名称/目录，不覆盖失败或成功

## 交接与边界

本轮 ROS 2 14 个配置和本分支一个配置合计 15 次实际完整回放，各配置一次；板端结束审计无旧作业活进程。两个目标分支独立提交，元数据/调用修正不重建或重放已接受数据。迟到通知按事件路径/SHA256 去重，不因旧失败回退有效环境；未删除网络积压消息

RK3588S 的 perf 计数/采样与 ROS 2 VINS PMU 已在所属分支验收，板端权限保持原值 2，DDR/功耗没有有效接口。真实相机、RGA/自研 NEON/NPU、回环/GNSS/KITTI/RViz 仍未完成数据验收；不自动重启桌面/神经网络历史批次。板端墙上时钟未同步，按主机阶段 UTC 与单调计时汇总

## 2026-10-14 推送边界核查

代码/文档/工具在主机，板端只有主机部署的运行包/脚本与数据/输出，未建立 Git 仓库。有效运行包 11251 文件保持主机清单哈希，29 个旧作业的 441 个 logs 文件全部在主机有相同 SHA256 副本，无遗漏待回收代码/文档/实验日志；本次只读审计结果也已回收

用户现授权核验后推送 master、ros2-humble、codex/rk3588-ros1、codex/rk3588-ros2 及新增所属 annotated tag，fast-forward/新增 refs，历史 tag 不移动、未使用复现支线不推。完整发布前检查归档在 ROS 2 目标分支 infra/rk3588/reference/publication_check_20261014/；历史冻结“未 push”为当时状态，保持原样

## 普通用户部署入口（2026-10-15）

ROS 1 当前版本定为 v0.1，完整交付目录 `/home/eric/projects/releases/ros1-v0.1/`；压缩包解压顶层为 install，板端默认 `~/vins-workspace/releases/ros1-v0.1/install/`。无需在板端搭建 ROS/OpenCV/Ceres 环境；部署、检查、回放、回收日志和自定义项目说明见 [第 11 份用户指南](11_RK3588_USER_GUIDE.md)

该版本保持原二进制/算法；目录重排、环境入口与打包器独立管理，旧冻结包不动。ROS 1 原清理 abort 与真实相机尚未验收的边界仍保留，不称完整生产稳定性通过；普通用户不再从旧 jobs 或 .infra 中挑选产物
