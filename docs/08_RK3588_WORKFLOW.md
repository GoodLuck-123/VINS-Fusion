# RK3588 ROS 1 交叉编译与远端工作流

更新日期：2026-10-14

本分支 codex/rk3588-ros1 从 ROS 1 master 最新 8c7c8d2 继续。主机联网下载/交叉编译，板端离线运行；原 master 和 ROS 2 分支/tag 保留，不将 ROS 2 核心合入本分支。实测写第 05 份报告，依赖锁见第 09 份文档

## 已验收与待验收

五包/六程序/70 个 ARM ELF 主机构建通过，tag milestone-rk3588-ros1-cross-build-v1；固定 OpenCV 4.2.0/Ceres 1.14.0/Eigen 3.3.9 的实际 RK3588 GFTT/LK/两种稀疏求解通过，tag milestone-rk3588-ros1-legacy-libs-v1。Noetic/Python 3.8 运行包主机准备完成，4209 文件/105 个运行库；节点生命周期和完整 VIO 仍待板端验收

## 一个命令下载与隔离构建

从仓库根、全新 bash 执行，不 source 桌面 ROS 或另一交叉工具链环境：

```bash
python3 infra/dependencies/fetch.py
bash infra/rk3588/scripts/build_legacy.sh
bash infra/rk3588/scripts/build_ros1_cross.sh
python3 infra/rk3588/scripts/verify_ros1_cross.py --output 新验证文件.json
```

GCC 9.4/Focal 工具链保留原 Carotene 参数，主机库只暴露编译器/ARM binutils 支持库，系统 CMake 使用主机 libc/libstdc++。SDK 绝对链接与 CMake 目标库/头文件导出可重复重定位，原包 SHA256 不改。cv_bridge 1.16.2 下载 C++ 源码原样，只在构建副本关闭可选 Python 扩展；主机 Python 3.10 仅运行纯 Python catkin/empy

输出为 ../.infra/rk3588/ros1-legacy/ 与 ros1_ws/devel/。原工程缺少全套 install 规则，打包脚本从核验过的运行文件生成可部署包，保留节点、闭包、资源和标定，避免复制完整 SDK/源码作为部署办法

## C++ 文件传输与运行工具

infra/remote/ 与 ROS 2 分支已验证工具源码字节一致，Linux/POSIX C++17 + OpenSSH 实现，跨 x86/ARM；初次从本分支 clone 时可独立编译：

```bash
cmake -S infra/remote -B ../.infra/remote-build -DCMAKE_BUILD_TYPE=Release
cmake --build ../.infra/remote-build -j4
cmake --install ../.infra/remote-build --prefix ../.infra
../.infra/bin/vins-remote firefly@10.106.0.220 文件或目录
```

默认已用本机专用密钥完成免密 SSH，新开发机自行生成并授权密钥，不复制私钥/密码或旧聊天 hook。一次调用上传、运行本地脚本并回收 logs；远端失败也先回收，结果目录拒绝覆盖，断线后用 --collect 回收同一作业，不重新执行

## 独立 Python 3.8 运行包与节点检查

```bash
python3 infra/rk3588/scripts/prepare_ros1_runtime.py \
  --build-commit milestone-rk3588-ros1-cross-build-v1 \
  --output ../.infra/rk3588/新运行包目录
bash infra/rk3588/scripts/deploy_ros1_runtime.sh \
  firefly@10.106.0.220 ../.infra/rk3588/新运行包目录 \
  ../results/rk3588/新运行环境阶段/board
```

Python 3.8/Noetic 为私有前缀，沿用 Ubuntu 22.04 板端 glibc/loader，不替换系统 Python 3.10，不在板端下载。ROS Python 启动器通过 PATH 选择私有解释器，文件清单冻结改后的 SHA256。SDK cv_bridge/cv2 排除，VIO C++ cv_bridge/OpenCV 来自本分支重建

部署探针验证文件哈希、Python 3.8/NumPy/rosbag 导入、实际动态库、ROS master 和图像/IMU 订阅，无传感器输入。原 ROS 1 未 join 的同步线程清理 abort 如实单列；不能称为正常退出，也不能将探针通过当作完整 VIO。后续完整回放每配置一次，原节点实收计数没有新增，bag 计数与末帧证据明确区分

## 串行实验和证据

板端同时只运行一批实验。已有 ROS 2 DMA heap 批次进行时，本分支只在主机准备，不上传或启动另一个板端探针。大批次由本地后台 run_local_phase.py 承接，结束/失败只通知当前聊天一次，不在线轮询；事件按路径/SHA256 去重

资源报告 VINS 全线程 CPU、每进程 RSS/PSS、回放与排空；没有采源端时标明不可用，不冒充合计 CPU。DDR/功耗不可用。保存原日志、源码/运行包来源和 SHA256，排空后通过不称为实时性验收，依赖传递差异不只归因于 ROS 版本
