# 重建入口检查

将 native_entrypoint_smoke.py 复制到仓库 `.local-tests/`，在 source ROS 2 专用环境后执行 `python .local-tests/native_entrypoint_smoke.py --output ../results/ubuntu22-reproduction/新目录`。结果目录拒绝覆盖，测试配置只改变输出路径

检查 loop/global 原生节点存活启动并 SIGINT 退出 0，以及两个 KITTI 入口缺少参数时退出 1。VINS 的两轮完整回放另验证启动/退出。这里没有回环、GNSS 或 KITTI 数据验收
