# Ubuntu 22.04 / VINS-Fusion ROS 2 Humble

## 分支与范围

`master` 保留 ROS 1 Noetic 原版参照；`ros2-humble` 作为 ROS 2 版本独立维护。两个版本使用仓库父目录下独立的安装与构建前缀，不创建根目录软链接。从仓库根目录执行本页命令。切换分支前检查 `git status`，在新终端激活对应环境。源码工作树随分支切换；切换版本后运行该分支的 build 脚本，再执行实验，避免源码和二进制版本混淆

迁移覆盖四个 package 及 KITTI 入口；EuRoC 单目 IMU 和双目 IMU VIO 均已完成实际回放。回环、GNSS、KITTI 数据及 RViz 的完整功能验收另列，不用 VIO 成功代替它们的验收。RealSense 等 ROS 1 硬件 launch 不属于本轮 EuRoC 迁移范围

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

保留原配置的标定、特征数、反向光流、跟踪图发布、线程模型、隔帧后端入队、3 ms 双目配对和求解器时间预算。首轮迁移参照保持原来的 `toCvCopy` 和 `clone`；当前版本默认 `image_mode=share`，可选择 `copy` 恢复原图像入口用于 A/B。此阶段不加入 RGA、NEON，不修改特征提取、光流或求解器计算。输入使用同一个 MH_01_easy 序列、原始时间戳和像素，评估使用相同 IMU/body 真值和 SE(3) 对齐，不校正尺度

Ceres 导出的 CMake 配置包含其构建环境的依赖路径，因此在两个环境中分别编译同版本 Ceres/OpenCV。构建并加载时必须检查实际路径，不能只检查版本字符串。ROS 2 的运行时、头文件和链接命令不得混入 ROS 1 前缀。OpenCV 不启用 VINS 未使用的 G-API/ADE，避免旧 ADE 在 GCC 13 上缺失标准头文件的兼容问题

## 重建与核验

首次搭建需要 Ubuntu 22.04 自带的 Python 3.10、curl、git 和 uv；无需预装系统 ROS、OpenCV/Ceres 或系统编译器。uv 安装方式及工作区布局见 [ROS 1 环境文档的首次搭建](02_UBUNTU22_ROS1_SETUP.md#3-首次搭建)

依赖约束见 `infra/desktop/environment-ros2.yml`，实际 linux-64 包及哈希固定在 `ros2-linux-64.lock`。Python 评估工具仍使用同一 `uv.lock`；ROS Python 与 uv 的虚拟环境分别使用，不在同一个终端叠加激活。原生工具、源码和数据由脚本下载至工作区，不运行 sudo 或改动系统包源

```bash
git switch ros2-humble
bash infra/desktop/scripts/bootstrap_ros2.sh
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/verify_ros2_environment.py
```

仅增量编译时执行 `bash infra/desktop/scripts/build_ros2.sh`。原生依赖重建使用 `build_ros2_native.sh`。默认构建并发为 4，可设置 `VINS_BUILD_JOBS=2`。锁文件当前只固定 linux-64；以后移植 ARM 时重新求解该平台锁，并从源码重建，不能复制 x86 二进制前缀

## 数据和完整实验

### 组件入口

`vins_ros::VinsNode` 可作为共享库动态加载，也可通过原有 `vins_node config.yaml` 独立运行。组件把 ROS 接口封装为带 `NodeOptions` 的节点；同一容器中的数据源和 VINS 都启用进程内通信时，才能减少通信复制。外部 `ros2 bag play` 仍经过跨进程通信，单独把 VINS 放进容器不能消除这条边界

上游配置/发布器仍有全局状态，因此一个进程只允许一个 VINS 估计器，可与数据源等其他组件共存。重复加载会返回错误；卸载会停止同步和估计线程、销毁发布器；支持卸载后重新加载单目/双目配置

```bash
export VINS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source infra/desktop/scripts/ros2_env.sh
ros2 launch vins euroc_components.launch.py config:=/absolute/config.yaml
```

本机 WSL 的动态加载服务在默认 Fast DDS 下未能完成请求响应；标准服务探针也复现，Cyclone DDS 下加载/卸载通过。因此组件服务入口在本机使用已包含在锁文件中的 Cyclone DDS，未升级原生依赖。原始参照及独立入口的 Fast DDS 设置保留；改变 RMW 的实验必须单独标记，不与原始结果混成同条件对比

### 图像所有权与共享路径

默认原生 `mono8` / `8UC1` 输入使用 `toCvShare`，不复制消息像素、不额外 `clone`。同步线程持有上一左图的消息 owner，直到下一次 `trackImage` 返回才替换，保证 `prev_img` 的底层内存仍存活。右图 owner 保持到当前跟踪结束；颜色转换、字节序不匹配等情形允许 cv_bridge 分配输出，不能称为所有输入零拷贝。前端只读使用这些视图；金字塔、跟踪图、回环长期图像等计算产物和必要复制仍保留。若今后启用原地修改图像的预处理，必须先建立可写的独立输出

单目和双目共用同一图像适配器与 owner 规则。`copy` 保留历史入口，包含 `8UC1` 消息复制，便于隔离减拷贝效果。停止并卸载组件时同步/后端线程先 join，再释放发布器与图像 owner；估计器拥有的积分对象在销毁时回收

```bash
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_mono_share1 --mode mono_imu --image-mode share
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_stereo_copy1 --mode stereo_imu --image-mode copy
```

真正的同进程 EuRoC 数据源 + VINS 链路：

```bash
export VINS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_composed_share1 --deployment composed --image-mode share
```

`vins_ros::EurocPlayer` 从 rosbag2 反序列化 typed 消息，再移动消息给 VINS；磁盘读取/反序列化仍有分配和复制。等待传感器和完成通知订阅就绪、延迟 3 秒后按记录时间回放。保留传感器 header/记录时间，每条传感器记录更新 `/clock`。runner 检查全序列传感器数量、共享/物化统计，以及起始图像在数据源、订阅端、视图之间的指针关系。这里采样整个容器、VINS 和数据源；不能与旧报告仅 VINS 的 CPU/RSS 直接计算加速比。`--deployment component` 仅把 VINS 放入容器，继续使用外部 `ros2 bag play`；主要用于接口/生命周期回归

### 数据转换和独立入口

普通终端执行转换与校验：

```bash
bash infra/desktop/scripts/convert_euroc_ros2.sh
```

转换为 Humble 可读的 SQLite rosbag2，逐消息比对全部共同传感器字段、像素、IMU 协方差、frame ID、header 和 bag 记录时间。ROS 1 的 `Header.seq` 在 ROS 2 中已移除，除此以外不改变传感器输入。校验结果保存在 `../results/ros2/bag_conversion.json`

ROS 2 终端运行：

```bash
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH_01_easy_ros2_metrics1 --rate 1
```

脚本等待订阅就绪，启用 `use_sim_time`，按 Reliable QoS 完整回放，然后等待后端输出稳定。保持订阅深度：双目各 100、IMU 2000。使用独立 ROS domain 和 localhost 通信。结果目录不允许覆盖；重复实验使用新的 `--name`

普通终端评估：

```bash
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python \
  infra/desktop/scripts/evaluate_baseline.py ../results/ros2/MH_01_easy_ros2_metrics1 --label "VINS ROS 2"
```

也可使用 `ros2 launch vins euroc.launch.py config:=/absolute/config.yaml loop_fusion:=false`。启动前在 YAML 中设置实际存在、可写的绝对输出路径；原版 YAML 的 `~/output` 不会由 OpenCV 自动展开。launch 不负责生成实验配置、回放或采样，正式对比使用上述 runner

## 验证和资源指标

临时开发探针位于 `.local-tests/`，已被 Git 忽略；包括算法改动范围检查、受控进程采样测试和节点启动/退出检查。可复现实验所需的构建、回放、校验与评估脚本纳入 Git。原始数据、安装前缀和完整日志不入库

| 类别 | 指标及口径 |
| --- | --- |
| 正确性 | ATE、相邻位姿 RPE、匹配率、输出数量、末帧覆盖、失败/配对丢弃、ROS 2 收到的传感器数量 |
| CPU | 进程累计 CPU 秒、平均单核百分比、1 秒采样的 p50/p95/p99；包含进程的所有线程 |
| 内存 | RSS 采样峰值、内核记录的 RSS 高水位、PSS、Private Dirty、线程峰值、主/次缺页 |
| I/O | 进程 rchar/wchar、read_bytes/write_bytes；缓存命中时物理读字节可能为零 |
| 主线程调度 | 自愿/非自愿上下文切换；不能当作全部工作线程的切换总量 |
| 系统压力 | CPU/内存/I/O PSI 与主机 loopback 字节增量，包含其他进程活动 |
| 吞吐 | 完整 1 倍速回放耗时、轨迹覆盖、回放后稳定等待；不把隔帧位姿数量当作输入丢帧 |

CPU 百分比以一个逻辑核为 100%，可能超过 100%。采样窗口为订阅就绪至回放后稳定，包含播放器的启动延迟和稳定等待。CPU 的采样分位数不是前端/后端单帧延迟；当前未侵入算法添加精细 profile。loopback 和序列化输入字节数用于理解传输压力，不代表 DDR 带宽，也不证明端到端零拷贝。WSL 未采集内存控制器带宽、硬件 cycles/cache misses、温度或功耗；此轮不引入额外系统工具来强行采集。实验串行执行，期间停止构建；仍需记录 WSL/宿主负载，少量重复结果不用于宣称统计性能提升

四个 package 和重建的 cv_bridge 已编译通过；三个主节点启动和 SIGINT 正常退出、KITTI 参数检查已通过。原版的同步线程退出 abort 与 ROS 2 全局发布器/后台线程的销毁顺序在迁移中处理；核心计算范围检查通过。两个版本各完成两轮完整 MH_01_easy 实验，结果见 [ROS 1 / ROS 2 对比报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

后续组件化/减拷贝版本另完成八轮完整实验：双目独立节点 copy/share 各两轮、双目同进程数据源 copy/share 各一轮、单目独立节点 copy/share 各一轮。单目两条路径的 ATE 均为 0.185564 m；每轮处理 3682 张图像、36820 条 IMU，正常退出

组件单目/双目反复加载和卸载、重复实例拒绝、无效配置拒绝通过；图像 owner、非连续 stride、转换回退和前端 copy/share 特征一致性通过本地探针。ASan 仅用于适配器/测试可执行文件，依赖库未全部插桩、泄漏检测未启用；其启动期加载器故障通过仅测试进程设置 `LD_BIND_NOW=1` 后连续三轮通过。这些探针不能代替板端长期稳定性验收。当前双目 share 的整体 CPU 均值略高，入口减拷贝成立，但没有整机提速结论

今后的版本对比统一追加到上述报告，不重写历史结果。先完成回放和同口径 evo 评估，再用 `append_euroc_comparison.py --section 唯一标识 --title "实验标题" 结果目录...` 追加表格并冻结小体积快照。各轮参数、源码和二进制哈希、RMW、资源采样范围必须留在 `run.json`，组件容器与独立节点的口径区别须保留

### 硬件计数器

普通终端可读取能力清单，不安装系统工具、不改内核权限：

```bash
python3 infra/desktop/scripts/probe_hardware_metrics.py --output ../results/ros2/hardware_probe_new.json
```

文件不得覆盖；输出不存在的 DDR/功耗值为 null。PMU 名称存在不等于有可用字节计数；虚拟电池读数不作为功耗。当前 WSL 核验 CPU PMU 可用，DDR 控制器事件、RAPL energy_uj、物理 hwmon 功率读数均未暴露

ROS 2 终端可额外记录 VINS 进程全部新建线程的用户态 CPU 事件：

```bash
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_stereo_pmu_new --image-mode share --perf-counters
```

通过同 PID 的启动门控，在原生程序建立工作线程前设置 inherit 计数器。事件包含 cycles、instructions、cache references/misses。计数在正常退出后读取，包括启动、稳定等待和退出；与原来的 subscription-ready-to-drain CPU 采样窗口有区别。各事件保留 time_enabled/time_running，未自动修正 multiplex；失败事件保留原因，不用零值伪装成测量结果。虚拟化 PMU 的 cache misses 仅为诊断，不乘 cache-line 大小换算 DDR；这里没有测量功耗

## 参考

- [RoboStack 隔离环境说明](https://robostack.github.io/GettingStarted.html)
- [ROS 2 Humble rclcpp 源码](https://github.com/ros2/rclcpp/tree/humble)
- [cv_bridge 3.2.1 官方源码](https://github.com/ros-perception/vision_opencv/tree/3.2.1)
- [rosbags 文档](https://ternaris.gitlab.io/rosbags/)

## EuRoC 跨进程共享像素与 DMA-BUF

`split` 使用两个原生进程：`euroc_player_node` 读包，`vins_node` 做 VIO。IMU、时钟和完成通知仍走 ROS 2；图像可选标准 Image、memfd 或真实 DMA-BUF。同进程组件及普通节点用法继续可用，默认 `image_transport=ros`

源数据反序列化后，memfd/DMA-BUF 路径各复制一次像素到 32 槽位有界池；通过 Unix socket 的 SCM_RIGHTS 注册实际句柄，只发送逐帧元数据。消费端只读映射，并在当前帧和上一左帧不再使用时归还槽位。没有后台驱动、系统服务或永久设备权限改动。异常/对端退出会结束本次实验；当前原型不支持热重连、多消费者或相机热切换

本次 WSL 内核无 dma_heap/udmabuf，可加载 VGEM 提供真实 DMA-BUF。VGEM 是软件 DRM 分配器；EuRoC 回放没有相机 DMA、RGA 或其他硬件参与。CPU 映射访问使用 `DMA_BUF_IOCTL_SYNC` START/END；缓冲生命周期协议负责防止同时改写，SYNC 本身不是互斥锁。参见 [Linux DMA-BUF 接口](https://docs.kernel.org/driver-api/dma-buf.html)

仅 VGEM 路径需要设备准备（已有权限时无需重复执行）：

```bash
sudo modprobe vgem
# 确认本机 VGEM 对应的 card 节点；card0 是本次 WSL 实际节点。
sudo chown "$USER" /dev/dri/card0
```

只改变本次设备节点所有者，模块重载/重启可恢复。程序核验 DRM 驱动名必须为 vgem，不会对其他 GPU 自动尝试分配。memfd 不需要 sudo。已有具备权限的 DMA heap 可用 `--image-transport dma_heap --shared-device /dev/dma_heap/system`；该后端本机未测试，不自动回退，也不代表支持任意 ARM 驱动。SDK 已锁定的 OpenSSL 3.6.5 提供 SHA256，未升级 OpenCV/Ceres 或引入系统 OpenCV/libdrm

统一 ROS 2 终端（三条路径都设置同一个 RMW）：

```bash
export VINS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/infra/desktop/cyclonedds_wsl.xml"
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_split_ros_new \
  --deployment split --image-mode share --image-transport ros
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_split_memfd_new \
  --deployment split --image-mode share --image-transport memfd
python infra/desktop/scripts/run_ros2_euroc.py --name MH01_split_vgem_new \
  --deployment split --image-mode share --image-transport vgem --shared-device /dev/dri/card0
```

单目视惯为相同命令添加 `--mode mono_imu`，使用新的 name；源端过滤右图。逐条串行运行，实验期间停止构建。Fast DDS 的首个 split 启动探针停在数据源订阅就绪等待，未产生轨迹，因此本次完整对照统一用已锁定的 Cyclone DDS；默认 Cyclone 大图像也出现延迟/丢弃；短回放证实进程级 XML 将 MaxMessageSize 设为 1400 B、FragmentSize 设为 1024 B、接收缓冲请求设为 4 MB 后可正常传输，避免本机镜像网络的大包 IP 重组问题

不改系统 sysctl，三条正式路径统一此配置。配置及 SHA256 随每轮归档；见 [Cyclone 0.10.5 配置原理](https://cyclonedds.io/docs/cyclonedds/0.10.5/config/cyclonedds_specifics.html)。失败记录留在本地，不能混入性能表。默认普通节点的 RMW 未改；其他环境需重新验证这个传输配置

每轮启用逐帧有效像素 SHA256，并将 header 时间戳与摘要累积为每摄像头签名；源端/消费端必须一致。共享路径核验导入 fd 的内核对象身份和长度、独立 PID、代次、完整帧数与正常退出。数据源与 VINS 分别留 CPU/RSS/PSS/线程/缺页采样；联合 CPU 为两进程 CPU 秒之和，RSS/PSS 峰值分别列出，不相加伪装同时峰值。校验本身有计算成本，不与此前未启用 SHA256 的结果直接算加速比

普通终端仍使用同一 uv 环境评估，然后用 `append_euroc_comparison.py` 追加到 [统一对比报告](05_EUROC_ROS1_ROS2_COMPARISON.md)。本地压力探针留在 Git 忽略的 `.local-tests/shared_probe.cpp`，正式回放/采样/评估脚本与小体积证据快照纳入 Git。该探针使用单独 ASan 可执行文件和非 PIE 链接规避 WSL 启动期加载器异常；不是全工程依赖插桩或长期泄漏验收

通用边界：当前共享协议限同机 Linux、单生产者/单消费者、线性 8 位灰度帧，EuRoC 数据源池为 752×480。只读视图、stride 和 owner 规则可复用；新相机仍需数据源适配、格式/布局协商、驱动导出能力及硬件 fence 验证。普通 ROS Image 是通用回退。不能将 VGEM 跑通等同于换相机即用或板端 DMA/RGA 验收。DDR 与功耗仍无可用硬件接口

## 版本里程碑与切换

过去的版本可以补 annotated tag，tag 直接指向原提交，不会移动分支；`master` 仍为 ROS 1 参照

| tag | 内容 |
| --- | --- |
| `baseline-ros1-euroc-v1` | ROS 1 隔离环境、原版 EuRoC 参照 |
| `baseline-ros2-humble-v1` | 最小 ROS 2 迁移与初始对比 |
| `milestone-ros2-components-v1` | 组件、图像 owner、单目/双目减拷贝对比 |
| `milestone-ros2-pmu-v1` | PMU 与 DDR/功耗能力核验 |
| `milestone-ros2-shared-memory-v1` | EuRoC 跨进程共享像素的完整实验 |
| `milestone-ros2-dmabuf-v1` | 真实 VGEM DMA-BUF 的完整 EuRoC 实验 |
| `milestone-ros2-shared-repeats-v1` | 三种传输 × 单目/双目 × 各 5 次串行完整实验及重复性结论 |

共享内存与 DMA-BUF 两个里程碑已按验收结果分别提交报告并打 tag；共享内存里程碑源码包含同接口的 DMA-BUF 后端，DMA-BUF tag 标识其独立数据验收完成，不表示相机 DMA 或 RGA 已完成。重复实验里程碑记录后续 30 次串行完整回放及统计审阅。后续每个小目标在实现、验证及文档归档完成后打 annotated tag；已发出的 tag 不移动

```bash
git tag --list
git switch --detach milestone-ros2-components-v1
# 如需在该版本继续修改：
git switch -c experiment/from-components milestone-ros2-components-v1
# 回到当前 ROS 2 主线：
git switch ros2-humble
```

切换源码后要重新 source 对应 ROS 环境并构建，tag 不切换 `.infra` 中的现有二进制。ROS 1/ROS 2 各自有独立前缀和构建目录，不能拿旧 install 验证新 checkout。所有 tag/提交目前保存在本地，不自动 push

本轮验收结果：六轮完整单目/双目回放，三种传输逐帧像素与 header 时间戳签名相同，每轮处理 3682 帧左图、36820 条 IMU，正常退出。memfd/VGEM 未归还槽位均为 0。VGEM 双目虽然完整处理数据，但背压令回放墙钟达到 206.84 秒（ROS 对照 188.77 秒），未通过稳定实时性验收；单目 VGEM CPU 同样高于对照。VGEM tag 标识真实句柄/完整数据功能实验完成，不标识加速完成。默认保留普通 ROS 路径；实际板端需选择适合 CPU 读图的缓存属性，再与硬件流水线共同验证。详见统一对比报告末节

## 三种传输的后台串行重复实验

`run_shared_repeats.py` 在新终端的普通系统 Python 下运行，内部按任务分别启用隔离 ROS 2 和 uv 评估环境。默认 3 种传输 × 单目/双目 × 5 次，共 30 次完整 MH_01_easy 回放；不复用先前单次结果。每个重复编号内轮换 ROS/memfd/VGEM 顺序，单目/双目块顺序交替。五次不能完全平衡所有排列，位置出现次数相差最多一次。每轮回放、正常退出和 evo 评估完成后间隔 10 秒，再启动下一轮；不同时启动多套 VINS

```bash
# 当前源码和脚本先提交；保持 VGEM 节点可访问，不在实验期间构建或改源码。
python3 infra/desktop/scripts/run_shared_repeats.py --batch shared_repeats_new --dry-run
nohup python3 infra/desktop/scripts/run_shared_repeats.py --batch shared_repeats_new \
  > ../results/ros2/shared_repeats_new.controller.log 2>&1 < /dev/null &
```

启动时检查没有其他 VINS/player/组件容器运行，检查已提交工作区和原生依赖隔离。每轮前后核验冻结源码、二进制、算法配置和 DDS XML 的哈希；目标倍率为 1，全帧 SHA256 保持开启。失败立即停止，保留失败目录与已完成轮次，不把不完整数据混入统计。WSL 和宿主机需持续运行，避免睡眠或停止 WSL；没有固定 Windows 宿主频率/温度

后台任务不调用模型、不轮询对话。`--completion-hook /path/to/hook-argv.json` 可指定 JSON 字符串数组形式的本地回调，例如 `["python3", "/absolute/path/notify.py"]`；任务仅在完成或失败时调用一次，并把 `event.json` 的绝对路径作为末尾参数。当前会话的 Codex 回调和 thread ID 留在 Git 忽略的 `.local-tests/`，不修改全局 hooks、代理或认证配置。通知失败也保留事件及 `hook.log`；查看 `state.json` 能区分实验状态和通知状态

结果位于 `../results/ros2/<batch>/`，包含逐轮状态、控制台日志、`trials.csv`、`summary.json` 和 `summary.md`。成功后自动复制小体积证据到 `infra/desktop/comparison_reference/<batch>/` 并追加统一对比文档，保留历史内容；人工/完成 hook 审阅后再 Git 提交和打 tag。统计按传输和模式报告 CPU 秒中位数、四分位数、范围，以及同重复编号相对 ROS 的变化；另外记录墙钟、ATE/RPE、RSS/PSS、池等待和主机 PSI/负载。资源口径及 SHA256 成本与此前三路径试跑一致，不代表 DDR 或功耗实测
