# Ubuntu 22.04 / VINS-Fusion ROS 2 Humble

## 分支与范围

`master` 保留 ROS 1 Noetic 原版参照；`ros2-humble` 作为 ROS 2 版本独立维护。
两个版本使用仓库父目录下独立的安装与构建前缀，不创建根目录软链接。
从仓库根目录执行本页命令。切换分支前检查 `git status`，在新终端激活对应环境。
源码工作树随分支切换；切换版本后运行该分支的 build 脚本，再执行实验，避免源码和二进制版本混淆。

迁移覆盖四个 package 及 KITTI 入口；EuRoC 双目 IMU VIO 是本次实际实验的主范围。
回环、GNSS、KITTI 数据及 RViz 的完整功能验收另列，不用 VIO 成功代替它们的验收。
RealSense 等 ROS 1 硬件 launch 不属于本轮 EuRoC 迁移范围。

## 控制变量与隔离

| 项目 | ROS 1 | ROS 2 |
| --- | --- | --- |
| ROS | Noetic | Humble |
| OpenCV / Ceres / Eigen | 4.2.0 / 1.14.0 / 3.3.9 | 相同版本 |
| GCC / Boost / glog / SuiteSparse | 13.4 / 1.86 / 0.6 / 5.10 | 相同版本 |
| cv_bridge | 1.16.2 | 3.2.1，适配 ROS 2 消息 |
| C++ 标准 | C++11 | C++17，满足 ROS 2 接口要求 |
| ROS 前缀 | `../.infra/ros1` | `../.infra/ros2` |
| 视觉和求解器前缀 | `../.infra/legacy` | `../.infra/legacy_ros2` |
| 构建工作区 | `../.infra/vins_ws`、`bridge_ws` | `../.infra/ros2_ws` |

保留原配置的标定、特征数、反向光流、跟踪图发布、线程模型、隔帧后端入队、3 ms 双目配对和求解器时间预算。
图像入口仍保持原来的 `toCvCopy` 和 `clone`；此阶段不加入 RGA、NEON 或减拷贝。
输入使用同一个 MH_01_easy 序列、原始时间戳和像素，评估使用相同 IMU/body 真值和 SE(3) 对齐，不校正尺度。

Ceres 导出的 CMake 配置包含其构建环境的依赖路径，因此在两个环境中分别编译同版本 Ceres/OpenCV。
构建并加载时必须检查实际路径，不能只检查版本字符串。ROS 2 的运行时、头文件和链接命令不得混入 ROS 1 前缀。
OpenCV 不启用 VINS 未使用的 G-API/ADE，避免旧 ADE 在 GCC 13 上缺失标准头文件的兼容问题。

## 重建与核验

首次搭建需要 Ubuntu 22.04 自带的 Python 3.10、curl、git 和 uv；无需预装系统 ROS、OpenCV/Ceres 或系统编译器。
uv 安装方式及工作区布局见 [ROS 1 环境文档的首次搭建](UBUNTU22_ROS1_BASELINE_SETUP.md#3-首次搭建)。

依赖约束见 `infra/desktop/environment-ros2.yml`，实际 linux-64 包及哈希固定在 `ros2-linux-64.lock`。
Python 评估工具仍使用同一 `uv.lock`；ROS Python 与 uv 的虚拟环境分别使用，不在同一个终端叠加激活。
原生工具、源码和数据由脚本下载至工作区，不运行 sudo 或改动系统包源。

```bash
git switch ros2-humble
bash infra/desktop/scripts/bootstrap_ros2.sh
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/verify_ros2_environment.py
```

仅增量编译时执行 `bash infra/desktop/scripts/build_ros2.sh`。
原生依赖重建使用 `build_ros2_native.sh`。默认构建并发为 4，可设置 `VINS_BUILD_JOBS=2`。
锁文件当前只固定 linux-64；以后移植 ARM 时重新求解该平台锁，并从源码重建，不能复制 x86 二进制前缀。

## 数据和完整实验

### 组件入口

`vins_ros::VinsNode` 可作为共享库动态加载，也可通过原有 `vins_node config.yaml` 独立运行。
组件把 ROS 接口封装为带 `NodeOptions` 的节点；同一容器中的数据源和 VINS 都启用进程内通信时，才能减少通信复制。
外部 `ros2 bag play` 仍经过跨进程通信，单独把 VINS 放进容器不能消除这条边界。

上游配置/发布器仍有全局状态，因此一个进程只允许一个 VINS 估计器，可与数据源等其他组件共存。
重复加载会返回错误；卸载会停止同步和估计线程、销毁发布器；支持卸载后重新加载单目/双目配置。

```bash
export VINS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source infra/desktop/scripts/ros2_env.sh
ros2 launch vins euroc_components.launch.py config:=/absolute/config.yaml
```

本机 WSL 的动态加载服务在默认 Fast DDS 下未能完成请求响应；标准服务探针也复现，Cyclone DDS 下加载/卸载通过。
因此组件服务入口在本机使用已包含在锁文件中的 Cyclone DDS，未升级原生依赖。
原始参照及独立入口的 Fast DDS 设置保留；改变 RMW 的实验必须单独标记，不与原始结果混成同条件对比。

### 数据转换和独立入口

普通终端执行转换与校验：

```bash
bash infra/desktop/scripts/convert_euroc_ros2.sh
```

转换为 Humble 可读的 SQLite rosbag2，逐消息比对全部共同传感器字段、像素、IMU 协方差、frame ID、header 和 bag 记录时间。
ROS 1 的 `Header.seq` 在 ROS 2 中已移除，除此以外不改变传感器输入。
校验结果保存在 `../results/ros2/bag_conversion.json`。

ROS 2 终端运行：

```bash
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH_01_easy_ros2_metrics1 --rate 1
```

脚本等待订阅就绪，启用 `use_sim_time`，按 Reliable QoS 完整回放，然后等待后端输出稳定。
保持订阅深度：双目各 100、IMU 2000。使用独立 ROS domain 和 localhost 通信。
结果目录不允许覆盖；重复实验使用新的 `--name`。

普通终端评估：

```bash
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python \
  infra/desktop/scripts/evaluate_baseline.py ../results/ros2/MH_01_easy_ros2_metrics1 --label "VINS ROS 2"
```

也可使用 `ros2 launch vins euroc.launch.py config:=/absolute/config.yaml loop_fusion:=false`。
启动前在 YAML 中设置实际存在、可写的绝对输出路径；原版 YAML 的 `~/output` 不会由 OpenCV 自动展开。
launch 不负责生成实验配置、回放或采样，正式对比使用上述 runner。

## 验证和资源指标

临时开发探针位于 `.local-tests/`，已被 Git 忽略；包括算法改动范围检查、受控进程采样测试和节点启动/退出检查。
可复现实验所需的构建、回放、校验与评估脚本纳入 Git。原始数据、安装前缀和完整日志不入库。

| 类别 | 指标及口径 |
| --- | --- |
| 正确性 | ATE、相邻位姿 RPE、匹配率、输出数量、末帧覆盖、失败/配对丢弃、ROS 2 收到的传感器数量 |
| CPU | 进程累计 CPU 秒、平均单核百分比、1 秒采样的 p50/p95/p99；包含进程的所有线程 |
| 内存 | RSS 采样峰值、内核记录的 RSS 高水位、PSS、Private Dirty、线程峰值、主/次缺页 |
| I/O | 进程 rchar/wchar、read_bytes/write_bytes；缓存命中时物理读字节可能为零 |
| 主线程调度 | 自愿/非自愿上下文切换；不能当作全部工作线程的切换总量 |
| 系统压力 | CPU/内存/I/O PSI 与主机 loopback 字节增量，包含其他进程活动 |
| 吞吐 | 完整 1 倍速回放耗时、轨迹覆盖、回放后稳定等待；不把隔帧位姿数量当作输入丢帧 |

CPU 百分比以一个逻辑核为 100%，可能超过 100%。采样窗口为订阅就绪至回放后稳定，包含播放器的启动延迟和稳定等待。
CPU 的采样分位数不是前端/后端单帧延迟；当前未侵入算法添加精细 profile。
loopback 和序列化输入字节数用于理解传输压力，不代表 DDR 带宽，也不证明端到端零拷贝。
WSL 未采集内存控制器带宽、硬件 cycles/cache misses、温度或功耗；此轮不引入额外系统工具来强行采集。
实验串行执行，期间停止构建；仍需记录 WSL/宿主负载，少量重复结果不用于宣称统计性能提升。

四个 package 和重建的 cv_bridge 已编译通过；三个主节点启动和 SIGINT 正常退出、KITTI 参数检查已通过。
原版的同步线程退出 abort 与 ROS 2 全局发布器/后台线程的销毁顺序在迁移中处理；核心计算范围检查通过。
两个版本各完成两轮完整 MH_01_easy 实验，结果见 [ROS 1 / ROS 2 对比报告](ROS1_ROS2_COMPARISON.md)。

## 参考

- [RoboStack 隔离环境说明](https://robostack.github.io/GettingStarted.html)
- [ROS 2 Humble rclcpp 源码](https://github.com/ros2/rclcpp/tree/humble)
- [cv_bridge 3.2.1 官方源码](https://github.com/ros-perception/vision_opencv/tree/3.2.1)
- [rosbags 文档](https://ternaris.gitlab.io/rosbags/)
