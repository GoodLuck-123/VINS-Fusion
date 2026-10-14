# 阶段事件统一核对

核对日期：2026-10-14

通知会因网络延迟积压，不能按到达顺序重新修改代码。当前已一次性读取工作区全部 52 个 event/state 文件，覆盖 29 个阶段，包含 13 个 RK3588 阶段；同阶段事件与状态字段一致。验收结论和路径/SHA256 见 [统一账本](../infra/rk3588/reference/global_audit_20261014/event_catalog.json)

## 当前有效状态

| 环节 | 有效结果 | 处理结论 |
| --- | --- | --- |
| 桌面 Ubuntu | 全部 52 轮及交接已完成 | 旧通知不触发重跑或新修补 |
| 工具链 / SDK 包 | toolchain02、sysroot03、dependencies01 | 包锁有效；后续 sysroot 链接和 CMake 导出重定位仍必须保留 |
| ARM 视觉库 | legacy05 + legacy-smoke01 | 固定 OpenCV/Ceres/Eigen，板端计算和动态库验收通过 |
| ARM ROS 2 构建 | ros2-build04 | 五个包构建完成，76 个 ARM ELF 依赖闭包无缺库或 4.5 混链；板端 VIO 待验收 |
| 当前后台任务 | 无 | 主机无构建/实验残留，板端七个旧作业均已终止 |

主机只剩最初 Docker 准备服务的 failed 状态，没有活进程。未清除失败日志，也没有把失败状态当作仍在运行。Git 核心实现和 config 与桌面交接 7d42fac 一致，没有并发修改或合并冲突；本轮改变的是依赖准备、构建兼容和部署工具

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
