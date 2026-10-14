# ROS 1 ARM 交叉构建验收

ros1-build02 主机阶段退出 0，cv_bridge C++ / camera_models / vins / loop_fusion / global_fusion 五包完成。六个可执行文件含主 VINS、Calibrations、两个 KITTI 入口、loop/global；70 个 ARM ELF 的递归动态库闭包完整，无 OpenCV 4.5 或 SDK cv_bridge 混用，目标 compile_commands 路径核验通过

核心/config 与 ROS 1 master 8c7c8d2 一致。构建脚本起源 c67da46，SDK 原生导出重定位修复 926ba26；cv_bridge 下载 C++ 源码与专用构建副本字节一致，仅关闭 Python 可选目标，不提供目标 Python cv_bridge 扩展。GCC 9.4、OpenCV 4.2.0 / Ceres 1.14.0 / Eigen 3.3.9 保持原版本，SuiteSparse 等 Focal 传递依赖与 ROS 2 Jammy 存在差异

重建 bash infra/rk3588/scripts/build_ros1_cross.sh；核验 python3 infra/rk3588/scripts/verify_ros1_cross.py --output 新验证文件路径。有效输出 ../.infra/rk3588/ros1_ws/devel/，原版 GeographicLib 输出在其 build/global_fusion/ThirdParty/GeographicLib/，打包必须包含该库；不移动/重命名原源码目标

仅验收主机构建/闭包，没有板端 ABI、节点生命周期或 VIO 结论。六入口均可构建不代表 KITTI/回环/GNSS 已完成数据验收。板端须使用独立 Python 3.8 私有运行包，保留板端 Ubuntu 22.04 glibc/loader；当前 ROS 2 共享实验不重启
