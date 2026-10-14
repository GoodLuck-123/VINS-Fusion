# ROS 2 预编译消息的 libpython 路径未重定位

cv_bridge 配置通过，但构建要求主机根目录中的 /usr/lib/aarch64-linux-gnu/libpython3.10.so；来源为 Ubuntu Humble 消息导出的 INTERFACE_LINK_LIBRARIES 字面绝对路径，不是 Python3 查找结果

统一 SDK 解包规则仅在这些 ROS CMake 导出中为该 libpython 路径加 CMAKE_SYSROOT，保存变更文件及前后 SHA256，不改包锁、二进制或 VINS/ROS 核心代码。既有原始 SDK 和本失败原日志保留；下一阶段重新配置后构建
