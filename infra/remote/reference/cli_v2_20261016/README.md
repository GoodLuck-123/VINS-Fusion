# 远程工具 v2 验收（2026-10-16）

Quick Start 与完整功能见 docs/12_VINS_REMOTE.md，本目录为小型证据；全部原始日志在 summary.json 的 raw_logs 路径

原生 C++/真实 rsync 的 12 项集成测试、6 项发布脚本测试，以及安装时保留用户配置检查通过。真板覆盖默认环境、真实交互 PTY、双向传输哈希、完成前日志到达、异常退出、超时、detach/follow/stop/collect 和默认 run.py；另在隔离根目录完整验证新版 deploy.py

默认 install 指向原验收 ros1-v0.1/install，原 4217 文件清单通过；新工具只改变主机操作和反馈，不重放 VIO，不修改算法、v0.1 包或 ROS 2 分支。VINS 原清理 −6 保留，检查外层 0 不等于原 VINS 正常退出

JSONL 记录板端 UTC 与单调时钟，板端墙上时间未同步；不拿其与主机 UTC 计算延迟。成功解压的时间提示原样保存在 deploy_unpack.stderr；开发环境失败另见 failure_notes.md
