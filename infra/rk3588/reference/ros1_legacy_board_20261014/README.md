# ROS 1 固定视觉库板端计算验收

ros1-legacy-smoke01 实际 RK3588/Ubuntu 22.04 上退出 0，25 个非 glibc ARM 运行库 SHA256 与 ldd 通过，沿用板端 loader/glibc。OpenCV 4.2.0 在 stride=80 的 64×64 mono8 图检测八个角点，LK 位移误差小于 0.1 像素、输入只读；Ceres 1.14.0 使用 SuiteSparse/CXSparse 两后端求解 x=10

重建 prepare_legacy_probe.sh、执行 legacy_probe.sh，源与参数见已跟踪 probes/legacy/。这是 Focal/Noetic 的独立视觉库与实际板端计算验收，没有 ROS 1 节点/完整 VIO 或真实性能数据。板端 ROS 2 共享批次结束且审计无残留后串行执行；GCC 9.4/Focal 传递依赖不同于 ROS 2 GCC 11/Jammy，不将后续差异仅归因于 ROS 版本
