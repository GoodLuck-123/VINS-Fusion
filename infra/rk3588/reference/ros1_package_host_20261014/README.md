# Noetic 运行包主机准备记录

ros1-package01 在主机退出 0，4209 个文件 / 105 个运行库，全部 SHA256 已复核。VINS 与 C++ cv_bridge/OpenCV/Ceres 来自已接受 ARM 构建，独立 Noetic/Python 3.8 私有前缀；SDK cv_bridge/cv2 排除，运行包不含板端 glibc/loader，保留板端系统 Python 3.10

构建核心来源 30790b0，打包脚本和 runner 来源 37c9113，入口 prepare_ros1_runtime.py。ROS Python 启动器改用 PATH 选择私有解释器，改后文件 SHA256 已冻结；runner 只调整当前仓库路径与无 Git 时的来源记录，原 VINS/core/config 不变

仅为主机运行包准备，不是板端生命周期或完整 ROS 1 回放验收。候选目录 ../.infra/rk3588/ros1-payload/；部署/回放单调用脚本已跟踪，板端待当前 DMA heap 阶段结束后串行执行，不据主机退出 0 提前打板端运行环境 tag
