# ARM 基线准备失败

board-baseline01 数据上传及 bag SHA256 校验通过，但 rclpy 初始化时找不到 librmw_fastrtps_cpp.so。VINS/播放器均未启动，没有完整回放，不计入成功实验统计；原运行包仅包含 Cyclone DDS

补充使用同一已验签 ROS APT 索引固定的四个 Fast DDS ARM 包，独立 addon 保留原 SDK/运行包不变。先验证 Fast DDS 节点生命周期，再以新结果前缀继续基线；保留本次日志和数据，不重复上传数据
