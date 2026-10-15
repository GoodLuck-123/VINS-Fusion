# ros2 v0.1 安装包验收（2026-10-15）

完整包生成在主机 releases/ros2-v0.1/，不纳入 Git；本目录仅小型验收证据，summary.json 记录压缩包 SHA256、大小、完整文件计数、原运行文件来源与主机包装提交

ROS 1 默认部署，ROS 2 独立预研。打包重排目录，全部原 ELF/配置保持对应已验收 SHA256；node/组件启动检查未输入 bag，不产生新的完整 VIO 统计。ROS 1 原同步线程清理 abort −6 保留；不称干净退出或生产长期稳定性已通过

主机部署和调用均经 C++ scp/run/collect 工具，日志已回收；ROS 2 在同一 install 内分别验证 Cyclone DDS 和 Fast DDS。原历史归档/core/config 检查保持通过，历史 tag 不移动

本地运行 `python3 -m unittest discover -s infra/release -p test_workflow.py -v` 的四项检查通过：部署/调用与引号路径、拒绝覆盖、错误校验和、拒绝不安全归档路径；生成脚本语法按目标 Python 3.8/3.10 检查
