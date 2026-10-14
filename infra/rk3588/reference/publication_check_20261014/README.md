# 2026-10-14 用户授权推送前核查

代码/文档在主机 authoring，板端只有主机部署的运行文件/脚本及实验输出，没有本任务 Git 仓库。有效 ROS 2/addon/ROS 1 运行包共 11251 文件与原冻结清单一致，29 个旧作业的 441 个 logs 文件在主机结果目录均有相同 SHA256 的副本，无待回收日志、无活旧作业。本次只读核查脚本和结果已回收，板端没有需要额外提交 GitHub 的源码/文档

桌面/板端既有归档和历史 snapshot 检查通过，待推对象未检出私钥/GitHub token，tracked 内容不含下载依赖/构建库/bag；源码/配置和依赖锁、脚本、报告及小型证据在主机仓库。此检查是当前发布前状态，不覆盖前次实验交接快照或失败证据

用户新授权推送 master、ros2-humble、codex/rk3588-ros1、codex/rk3588-ros2 及缺失且属于这些分支的新增 annotated tag。仅 fast-forward/新增 refs，使用 atomic 推送，不 force，不推未使用的 codex/ubuntu22-ros1-reproduction，不移动已有 tag。此快照记录推送前检查，推送完成以后以远端 refs 验证为准
