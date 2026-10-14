# ROS 1 ARM 视觉库主机构建

ros1-legacy02 退出 0；Focal GCC 9.4 与独立 ros1-legacy 前缀，原 OpenCV 4.2.0/Ceres 1.14.0/Eigen 3.3.9。Ceres 保留 SuiteSparse/CXSparse/LAPACK 功能，库 ELF 为 AArch64

这是主机构建记录，不是板端计算/ABI 或完整 ROS 1 VIO 验收。消费端探针由 prepare_legacy_probe.sh 重建，用 vins-remote 和 legacy_probe.sh 执行；当前 ROS 2 完整共享批次结束后才使用板端，失败证据不覆盖

消费端实际链接成功，Ceres 导出组件包含 SuiteSparse/CXSparse/LAPACK/OpenMP，25 个非 glibc ARM 运行库闭包已打包；文件摘要见 probe_files.json。板端尚未执行，不能提前打板端视觉库验收 tag
