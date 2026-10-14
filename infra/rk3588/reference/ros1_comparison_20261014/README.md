# ROS 1 对照结果的跨分支摘要

本目录仅复制 ROS 1 已验收结果用于第 05 份统一报告，没有新增实验。完整原文件/解压前哈希与日志保存在 codex/rk3588-ros1 的 baseline-rk3588-ros1-v1 / commit 2d76d3a，路径 infra/rk3588/reference/ros1_baseline_20261014/

实际完整回放一次，原 VINS 清理 abort −6 单列；event.json 仍是主机评估参数失败的原事件，evaluation_recovery_event.json 是仅对已收轨迹补评估成功的事件。两者组成结果接受证据，未重新回放或改写失败；不能将原失败阶段改称成功

可用 git show baseline-rk3588-ros1-v1:infra/rk3588/reference/ros1_baseline_20261014/summary.json 读取完整归档入口。此处 summary.json 的原文件哈希对应 ROS 1 完整归档，当前摘要子集由 SHA256SUMS 独立校验
