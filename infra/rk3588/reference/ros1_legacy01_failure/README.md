# ROS 1 ARM 视觉库首次构建失败

ros1-legacy01 在 CMake 启动前退出 1，没有目标库构建。Focal 主机工具链全目录 LD_LIBRARY_PATH 抢占系统 libstdc++，Jammy CMake 需要 GLIBCXX_3.4.29/30，旧库不提供

cross_env.sh 改为仅暴露 GCC 9 必需的 isl/gmp/mpc/mpfr 主机库；目标依赖、编译器、OpenCV/Ceres/Eigen 版本和原 Carotene 参数均不变。重试另用新阶段目录，不覆盖失败证据
