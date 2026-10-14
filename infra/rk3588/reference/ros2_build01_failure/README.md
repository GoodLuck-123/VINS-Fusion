# ROS 2 ARM 配置阶段资源索引缺失

编译前 cv_bridge 配置退出 1，主机/目标 Python 与 Boost 查找均正确；typesupport 的 ament 资源索引未设置路径，报 No rosidl_typesupport_c found

包和索引已存在 SDK 内，构建入口显式设置 AMENT_PREFIX_PATH 为目标 install 与 SDK 的 ROS 前缀，不 source ARM shell 或执行 ARM 程序，未修改 ROS/VINS 核心源码
