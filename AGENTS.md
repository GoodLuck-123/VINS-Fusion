# Agent 工作约定

先读 docs/00_HANDOFF.md，按任务查阅第 05、08、11、12 份文档

- 仅在 codex/rk3588-ros1 开发；保留 master、ros2-humble、codex/rk3588-ros2 与历史 tag，不合并其他核心
- 主机下载/交叉构建，板端离线运行；源码、用户文档与工具在主机 Git，板端只部署运行材料
- 默认板端工作区 ~/vins-workspace，开发目录 projects/vins，当前入口 install，环境 install/env.sh。统一读取 infra/remote/vins-remote.conf 或其已安装副本；普通调用不用重复写路径，必要时用命令行覆盖
- 日常通过 vins-remote、deploy.py、run.py 操作和收日志；仅特殊调试手动 SSH，不保存密码，不另建常驻 RPC 服务
- 用户文档采用总分结构：先 Quick Start 常用命令，再说明配置、详细行为、异常和恢复。新增指南沿用编号；入口变化同步 README 和第 00 份文档
- 保留 OpenCV 4.2.0/Ceres 1.14.0、原算法和标定，最小改动；修改算法/传输后做局部正确性和完整串行 A/B；纯文档不重跑整批 VIO
- 默认路径变更不移动旧冻结包；install 只在验收后选定，拒绝覆盖真实目录。结果放 ../results/，构建前缀 ../.infra/，依赖占位下载内容在 dependencies/ 忽略
- 实验验收输入/初始化/重置/末帧/ATE/RPE/退出/共享槽位；CPU 全线程秒、各进程 RSS/PSS、回放/排空分别记录，缺 DDR/功耗写不可用，排空不等于实时
- 新结果续写 docs/05_EUROC_ROS1_ROS2_COMPARISON.md，小型证据与 SHA256 纳入 Git，完整日志在父工作区；历史数据/tag/失败证据不改写，积压通知按账本去重
- 必要工具探针可重建并跟踪；一次性草稿放 .local-tests/，不能作为依赖。大批次后台 runner 只在终止/需处理时通知，不用在线模型轮询
- 每个目标独立提交，验收后打 annotated tag，不移动旧 tag；按用户授权 push 所属分支/tag。Markdown 自然段末不加中文句号
