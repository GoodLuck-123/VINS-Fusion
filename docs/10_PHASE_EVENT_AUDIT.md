# 阶段事件统一核对

核对日期：2026-10-14

通知会因网络延迟积压，不能按到达顺序重新修改代码。当前已一次性读取工作区全部 52 个 event/state 文件，覆盖 29 个阶段，包含 13 个 RK3588 阶段；同阶段事件与状态字段一致。验收结论和路径/SHA256 见 [统一账本](../infra/rk3588/reference/global_audit_20261014/event_catalog.json)

## 当前有效状态

| 环节 | 有效结果 | 处理结论 |
| --- | --- | --- |
| 桌面 Ubuntu | 全部 52 轮及交接已完成 | 旧通知不触发重跑或新修补 |
| 工具链 / SDK 包 | toolchain02、sysroot03、dependencies01 | 包锁有效；后续 sysroot 链接和 CMake 导出重定位仍必须保留 |
| ARM 视觉库 | legacy05 + legacy-smoke01 | 固定 OpenCV/Ceres/Eigen，板端计算和动态库验收通过 |
| ARM ROS 2 构建 / 运行环境 | ros2-build04、runtime01、fastrtps02 | 五包构建、依赖闭包、节点/组件生命周期与完整部署哈希通过 |
| ROS 2 完整 VIO | baseline02、components01、pmu01 | 八轮去重配置完整输入/末帧/评估/退出通过，PMU 无错误或复用 |
| 共享计算探针 / 完整 memfd | shared-probe01、board-shared01 | 两后端计算探针与四轮完整共享 VIO 通过，槽位全部归还 |
| ROS 1 ARM | ros1-fetch01、ros1-legacy02、ros1-build02 | 依赖、视觉库与五包/六程序/70 个 ELF 闭包通过，视觉库实际板端计算通过，Noetic 节点/回放仍待验收 |
| 当前后台任务 | board-dma-heap01 | 板端实际 system DMA heap 双目/单目各一轮，串行运行 |

初次统一审计时主机只剩 Docker 准备服务的 failed 状态，没有活进程；后续任务见上表。失败日志保留，终止状态不当作仍在运行。Git 核心实现和 config 与桌面交接 7d42fac 一致，没有并发修改或合并冲突；本轮改变的是依赖准备、构建兼容和部署工具

## 失败与被替代阶段

| 阶段 | 结论与后续处理 |
| --- | --- |
| cross-sdk01 | Docker 失败，相关实现已 revert，使用私有交叉 GCC/SDK 替代 |
| legacy01 | Ninja 不存在，改用主机 Make |
| legacy02 | GCC 参数改名，应用仅改名称的 Carotene 补丁 |
| legacy03 | BLAS/LAPACK 目录与可选 TBB 探测问题，保留原求解器功能后重建 |
| legacy04 | 退出 0，但消费端链接失败；SDK 绝对符号链接和间接库路径修正后全量重建 |
| ros2-build01 | ament 索引路径缺失，显式设置目标前缀 |
| ros2-build02 | ROS 消息 CMake 导出的 libpython 路径未重定位，修正 SDK 导出 |
| ros2-build03 | 退出 0，但选中 SDK cv_bridge 并混链 OpenCV 4.5；固定重建包路径，独立 workspace 全量重建 |

legacy04、ros2-build03 均不计入成功统计，不能因通知写 complete 就恢复其产物。全部失败记录保留，原生归档、板端归档及最终依赖来源已统一复核，证据见 [全局核对快照](../infra/rk3588/reference/global_audit_20261014/)

## 后续处理规则

收到通知后先核对账本中的事件路径和 SHA256。已经登记、被替代或撤回的阶段只作为历史证据，不重新提交、修补或切换安装前缀；若相同路径的内容改变，应先调查，不把它当作自动重跑授权

新阶段按依赖顺序串行验收。使用当前有效前缀，不允许回退到失败或混链产物：

- ARM 视觉库：`../.infra/rk3588/legacy/`
- ARM ROS 2 install：`../.infra/rk3588/ros2_ws_overlay/install/`
- 旧 `legacy_before_sysroot_links/`、旧 `ros2_ws/` 仅留作失败追溯

本次已经读完磁盘事件；没有删除聊天队列中的消息。后续迟到消息仍按账本去重，不能根据消息到达时间改变代码或验收结论。新运行批次固定源码和产物，每次只保留一个活动实验批次，结束后统一读取状态再决定下一改动

## 核对后的新增阶段

runtime01 已接受为板端 ROS 2 运行环境验收，事件及逐文件 SHA256 见 [运行环境归档](../infra/rk3588/reference/runtime_20261014/)。远端校验 6991 个文件、独立节点与组件生命周期通过、退出 0，无 bag 输入，不是完整 VIO。对应迟到通知同样按归档事件路径与哈希去重，不重跑

board-baseline01 为补充依赖前的失败，数据已到板端并通过哈希；rclpy 找不到 Fast DDS 后端，尚未启动 VINS/播放器。事件和日志见 [失败归档](../infra/rk3588/reference/baseline01_failure/)，不得计入成功统计；先验收独立 Fast DDS addon，原已接受运行包不撤回

fastrtps01 为主机下载失败，HTTPS 仓库证书域名不匹配，没有解包/部署 addon。后续采用原 SDK 的 HTTP 仓库地址，版本和已验签索引的逐包 SHA256 不变，见 [失败证据](../infra/rk3588/reference/fastrtps01_failure/)

fastrtps02 已接受为 Fast DDS 板端生命周期验收，addon 与原运行包哈希、实际 maps 和退出均通过，事件/SHA256 见 [归档](../infra/rk3588/reference/fastrtps_20261014/)，无 bag 输入。旧 fastrtps01 通知只去重，不改回 URL 或重新下载

board-baseline02 已接受为首轮完整双目基线，输入计数、初始化/无重置、末帧、ATE/RPE、退出和结束进程审计通过。事件和 SHA256 见 [归档](../infra/rk3588/reference/baseline_20261014/)，旧 board-baseline01 启动失败不重新运行

board-components01 已接受为五轮单目/双目入口与 composed 对照，完整输入/末帧/退出、主机评估、入口及指针证据和结束审计通过，事件/SHA256 见 [归档](../infra/rk3588/reference/components_20261014/)。双目 standalone/copy 已在 baseline02 验收，不重复回放；后续旧通知只去重

board-pmu01 已接受为两轮完整 PMU 对照，四类事件无错误/复用，输入、末帧、评估、退出及结束审计通过，事件/SHA256 见 [归档](../infra/rk3588/reference/pmu_20261014/)。shared-probe-build01 只完成主机 ARM 构建，尚无板端缓冲/heap 验收，不将构建成功混入 VIO 成功统计

shared-probe01 已接受为 memfd/实际 DMA heap 计算探针，两后端各 1000 帧、失败和 outstanding 均为 0，结束审计无残留；事件与 SHA256 见 [归档](../infra/rk3588/reference/shared_probe_20261014/)。不是完整 VIO。重新读取全部当前 RK3588 event 后，fastrtps02、board-baseline02 与已接受事件逐字节一致，只去重；新 ROS 1 视觉库首次构建失败在独立 ROS 1 分支处理，不回退 ROS 2 运行包

ros1-sdk-discovery01 迟到事件与 ROS 1 分支已接受归档逐字节一致，只去重。ros1-legacy02 主机视觉库构建及独立消费端链接通过，证据位于 ROS 1 分支 infra/rk3588/reference/ros1_legacy_build_20261014/；板端计算和完整 ROS 1 回放待验收，ROS 2 当前仅 board-shared01 活动

board-components01、board-pmu01 两条迟到事件再次与已验收归档逐字节核对一致，只去重，分别对应 a545a95 / af6c635，不重复提交里程碑或重跑。ros1-build01 在独立分支保留失败证据；Noetic 原生库/头文件导出路径重定位后启动 ros1-build02，已进入原 VINS 编译，仍需完成闭包、板端 ABI 和回放验收

shared-probe-build01 与 shared_probe_20261014/build_event.json 逐字节一致，已包含在共享计算探针里程碑 8f04c3f，只去重。ROS 1 ros1-build02 已在所属分支验收并打 tag，主机退出 0 加 ELF/编译路径完整性核验通过；原 VINS/core/config 不变。ros1-package01 只负责新运行包准备，未部署、未进行板端 ROS 1 回放

board-shared01 四轮完整回放/主机评估、逐帧摘要与槽位归还已接受，事件/SHA256 见 [归档](../infra/rk3588/reference/shared_20261014/)，结束审计无活作业。ros1-fetch01 迟到事件与 ROS 1 分支冻结归档逐字节一致，只去重；ros1-package01 主机完成，板端运行环境仍待验收。ROS 1 视觉库的实际板端计算探针 ros1-legacy-smoke01 已通过，提交在其所属分支

board-dma-heap01 在完整共享里程碑 5e685b1 与 ROS 1 视觉库实际计算里程碑 6c4703a 均提交后启动，板端只有这一批活动 VIO；每配置一次、明确 system heap，无自动回退。ROS 1 运行包和生命周期脚本已在主机准备，待本批结束后再部署，不并发板端工作

shared-probe01 迟到事件与共享计算归档逐字节一致，SHA256 为 757f875ddf4c1a7a557a4182a39d399f5058e3d3979216ecb6a47464b9fd4055，只去重，里程碑 8f04c3f 不重复提交。ROS 1 分支已固定单调用完整回放入口并冻结主机运行包准备证据，板端部署/回放等待 board-dma-heap01 完成，不并行启动
