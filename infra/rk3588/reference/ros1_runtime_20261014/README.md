# ROS 1 Noetic 运行环境验收

ros1-runtime02 在实际 RK3588 Ubuntu 22.04 上通过 4210 文件 SHA256、私有 Python 3.8.10 / NumPy 1.17.4 / rosbag 导入、rosversion/roslaunch 1.17.4、VINS ldd 和双目图像/IMU 订阅就绪。实际 maps 为私有 OpenCV 4.2/Ceres/Python 与板端 libc，系统 Python/glibc 不替换，结束审计无旧任务活进程

ROS master 退出 0；原 ROS 1 同步线程未 join 的清理 abort 为 −6，与桌面原版一致，日志 terminate called without an active exception 保留。不称为正常 VINS 退出。没有 bag 输入、初始化/轨迹或 VIO 资源数据；完整回放后单独验收

运行包源码核心来源 30790b0，打包修复 9b426e8，实际候选 ../.infra/rk3588/ros1-payload02/；ROS 1 C++/算法/标定与 master 8c7c8d2 相同，源码未改。板端路径 /home/firefly/vins-workspace/jobs/1791970072506-133971/ros1-payload02，后续单调用 runner 默认核对本归档 payload_files.json，不复用旧失败包。第一次缺 rosversion 的失败独立保留
