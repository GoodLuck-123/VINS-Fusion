# ROS 1 首次运行环境部署失败

ros1-runtime01 主机/板端退出 1。4209 文件校验、私有 Python 3.8/NumPy/rosbag 导入与 VINS ldd 已通过；roscore 的 roscore.xml 调用 rosversion，但该 rospkg 脚本位于 SDK usr/bin，初次只复制了 opt/ros/noetic/bin，导致 roscore 退出 1。没有启动 VINS，没有传感器输入/完整回放

打包脚本最小补齐 SDK 原 rosversion 启动器并选择私有 Python，构建新候选目录，不覆盖首次运行包/失败日志。后续完整实验默认使用已验收归档的文件清单，避免误用旧候选清单；代码/依赖/算法/标定不改
