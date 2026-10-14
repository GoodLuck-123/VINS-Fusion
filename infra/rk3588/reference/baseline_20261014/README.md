# RK3588 ROS 2 双目基线

board-baseline02 完整回放通过，Fast DDS / standalone / copy，rate=1，原标定与算法参数。图像各 3682、IMU 36820、processed 3682，一次初始化、无重置或配对丢帧，1831 个姿态、1819 个真值匹配、末帧覆盖，VINS/回放均退出 0；阶段结束后无旧作业活进程

主机使用 desktop uv.lock/evo、SE(3) 无尺度校正评估，ATE/RPE 见 summary.json。资源只包含 VINS 全线程，原 standalone runner 没有采集 ros2 bag play 的 CPU/RSS/PSS，不能作为合计 CPU；后续 split 会分别记录。排空含五次稳定采样等待，不是逐帧实时性验收

运行包/addon/bag 全部哈希验证通过，核心/config 与 c0ae27d/桌面交接一致。完整日志、轨迹、资源、telemetry 和数据/部署来源均归档；原基线准备失败和旧混链构建不计入成功统计。板端墙上时间偏移，耗时用单调时钟，外层事件用主机 UTC
