# ROS 1 项目首次交叉构建失败

ros1-build01 配置成功，cv_bridge C++ 编译后链接失败，Noetic rosconsole 导出绝对 /usr/lib/aarch64-linux-gnu/liblog4cxx.so，CMake 未自动重定位该项。尚未构建 VINS，没有板端实验

统一 fetch.py 扩展目标原生库/头文件导出的重定位，包版本/SHA256 与原始下载包不变，逐文件原始/重定位 SHA256 写入独立 .vins-native-cmake-relocations.json；重复下载不重复加前缀。旧失败保留，重试新阶段目录
