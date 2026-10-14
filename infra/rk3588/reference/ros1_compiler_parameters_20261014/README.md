# Focal 交叉编译器参数核验

36 个工具链包下载/SHA256 校验完成，私有 GCC 9.4 --version 与空 C++ 翻译单元 ARM 对象编译成功。原 OpenCV 4.2 Carotene 的 ipcp-unit-growth 参数接受，GCC 11 使用的 ipa-cp-unit-growth 参数在 GCC 9.4 被拒绝；ROS 1 直接使用原源码，不套用 ROS 2 的参数改名补丁

这只验证主机编译器和参数，不代表目标 SDK、视觉库或板端 ROS 1 验收。探针可重建：设置私有工具链 usr/lib/x86_64-linux-gnu 为 LD_LIBRARY_PATH，分别执行 aarch64-linux-gnu-g++ --param=参数名=100000 -x c++ -c /dev/null -o /tmp/新的对象文件
