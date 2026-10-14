# ARM ROS 2 运行环境验收

主机 runtime01 事件退出 0，板端校验 6991 个文件 SHA256，rclpy/消息/rosbag2_py 导入成功。独立 VINS 节点和组件订阅就绪，组件卸载成功，两进程均正常退出 0；ldd 无缺库，进程 maps 中 OpenCV 均来自运行包 4.2

无 bag 输入，sensor_counts 全零；本探针不代表完整 VIO、精度或实时性验收。部署工具上传运行包并自动回收日志，未复制 SDK glibc/loader。板端墙上时钟未同步，外层事件使用主机 UTC
