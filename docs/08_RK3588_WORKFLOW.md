# RK3588 交叉编译与远端实验

更新日期：2026-10-14

本轮在联网 Ubuntu 主机下载、交叉编译和打包，离线板端执行，再自动回收日志。依赖、构建、节点生命周期、完整双目基线、单目与组件/owner 已验收；PMU/共享与 ROS 1 仍待验收。各配置只执行一轮，不运行历史重复批次或新的算法优化

## 当前环境与有效产物

目标 firefly@10.106.0.220，Rockchip RK3588S LP4X LIXU Board；Ubuntu 22.04.5/aarch64、厂商内核 5.10.110，4 个 A55 + 4 个 A76、约 16 GiB RAM、约 95 GiB 磁盘可用。root overlay 的 upper 在 userdata，不重启或替换系统；板端 sudo 非交互可用，下载只在主机完成

ROS 2 分支 codex/rk3588-ros2 从桌面交接 7d42fac 建立，ROS 1 板端代码另从 master 最新提交继续，不合并 ROS 2 核心。当前核心和 config 与桌面交接一致，板端依赖兼容修补、失败和传递依赖差异均单独保存

| 环节 | 当前有效状态 / 位置 |
| --- | --- |
| SSH / 远端工具 | 免密及 scp/运行/日志回收已验收，../.infra/bin/vins-remote |
| 下载与 SDK | 一条命令按固定版本/SHA256 补齐，见第 09 份说明 |
| 视觉库 | ../.infra/rk3588/legacy/，主机交叉编译与板端计算通过 |
| ROS 2 项目 | ../.infra/rk3588/ros2_ws_overlay/install/，五个包构建完成，76 个 ARM ELF 闭包无缺库或混链 |
| ROS 2 板端运行环境 | runtime01 通过文件哈希、导入、独立节点/组件生命周期，tag milestone-rk3588-ros2-runtime-v1 |
| profile | perf 计数/采样/函数符号解析通过，尚无 VINS 热点结果 |
| 单目与组件/owner | board-components01 五轮去重配置通过完整回放与评估 |
| PMU/共享与 ROS 1 ARM | 待完整运行与轨迹验收 |
| 完整双目基线 | board-baseline02 通过输入/末帧/退出及主机 ATE/RPE，资源范围见第 05 份报告 |

旧 ros2_ws/、legacy_before_sysroot_links/ 只保留失败追溯，不再作为有效部署输入。积压事件的统一结论和去重规则见 [第 10 份账本](10_PHASE_EVENT_AUDIT.md)，不要按通知到达顺序改代码

## 免密 SSH 与 C++ 远端工具

本机专用密钥 ~/.ssh/id_ed25519_vins_rk3588 已添加板端 authorized_keys，SSH config 只为该 IP 指定 IdentityFile，BatchMode 实测通过。密码和私钥不入 Git；其他开发机生成自己的密钥，不复制这台机器私钥。公开指纹和板端能力快照见 [连接证据](../infra/rk3588/reference/connection_20261014/)

辅助工程 infra/remote/ 使用 C++17 与系统 OpenSSH，面向 Linux/POSIX 主机，通过 SSH 跨 x86/ARM 通信；远端需要 bash、setsid、timeout

```bash
cmake -S infra/remote -B ../.infra/remote-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/g++
cmake --build ../.infra/remote-build -j4
cmake --install ../.infra/remote-build --prefix ../.infra
```

默认传文件或目录到 home 的 vins-workspace/incoming，也可指定目录：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 文件或目录
../.infra/bin/vins-remote firefly@10.106.0.220 install --dest vins-workspace/releases
```

一次调用上传 payload 与本地脚本，远端执行后自动回传结果；以下脚本名和结果名由实际阶段选择，脚本使用 VINS_REMOTE_PAYLOAD、VINS_REMOTE_ROOT 定位输入/作业目录，将需要回收的文件写入 logs 子目录：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 install \
  --run 本地实验脚本.sh --output ../results/rk3588/新结果名 --timeout 1800
```

作业目录唯一，回收 console.log、起止 UTC、退出码和脚本输出。远端失败也先回收日志再返回退出码，本地结果目录拒绝覆盖；SSH 中断时 detached 作业继续，按已打印的 job 路径回收，不重新跑：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 vins-workspace/jobs/作业名 \
  --collect ../results/rk3588/新回收名
```

scp 明确使用 legacy 模式固定 POSIX 路径转义，SSH/scp 均启用 BatchMode。真实板端测试覆盖空格/单引号路径、故意退出 7、失败日志回收和不重跑回收；连接测试不算 VIO 实验

## 主机下载与交叉构建

主机执行，不在 ARM 运行 desktop bootstrap，也不传 x86 install 代替重建：

```bash
python3 infra/dependencies/fetch.py
bash infra/rk3588/scripts/build_legacy.sh
bash infra/rk3588/scripts/build_ros2_cross.sh
```

依赖源码、交叉工具链与目标 sysroot 在 dependencies/ 的 Git 占位目录，下载内容忽略；构建、安装、数据与完整日志仍在父工作区。包锁、缓存复用、离线重跑以及 sysroot 链接/CMake 导出重定位见 [第 09 份说明](09_DEPENDENCIES.md)

工具链为主机 GCC 11.4.0 → aarch64，位于 infra/rk3588/cmake/aarch64.cmake；cross_env.sh 在新的 bash 中为配置与编译提供主机工具动态库和目标库查找路径。源码/依赖变化后重建，不复用旧 CMake 缓存或错误安装；不 source 桌面或 ARM ROS 环境来构建

视觉库固定 Eigen 3.3.9、OpenCV 4.2.0、Ceres 1.14.0，默认四个 Make 编译任务，可用 VINS_BUILD_JOBS 调整。Carotene 补丁只修正 GCC 参数名称，在独立源码副本应用；OpenCV 模块/关闭特性及 Ceres 求解器功能保留。传递依赖差异和板端计算探针见 [第 05 份报告](05_EUROC_ROS1_ROS2_COMPARISON.md)

ROS 2 直接 CMake 顺序构建 cv_bridge 3.2.1、camera_models、vins_estimator、loop_fusion、global_fusion。主机 Python 3.10 执行纯 Python ament/catkin 构建工具，Python/NumPy 头文件与 libpython 来自 ARM SDK；固定使用重建 cv_bridge/camera_models，防止 SDK OpenCV 4.5 混链。编译和 ELF 核验通过不等于回环/GNSS/KITTI或板端 VIO 数据验收

ROS 官方旧 cross_compile 工具已经停止支持，本工程使用明确 CMake 工具链/sysroot，[官方说明](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Cross-compilation.rst)

## ROS 2 运行包与部署入口

从已验收构建提交打包，再用一次调用完成 scp、板端检查和日志回收：

```bash
python3 infra/rk3588/scripts/prepare_ros2_runtime.py --build-commit c0ae27d
bash infra/rk3588/scripts/deploy_ros2_runtime.sh firefly@10.106.0.220 \
  ../.infra/rk3588/ros2-payload ../results/rk3588/新的运行环境检查
```

打包拒绝覆盖目录，核对核心/config 与构建提交一致；运行包包含 VIO 节点、插件、必要 ROS/Python 资源及动态依赖，排除静态库、KITTI 程序和 SDK cv_bridge/OpenCV 4.5，保留板端 glibc/loader。全部 ELF 校验 AArch64，生成逐文件 SHA256 和构建来源记录；部署环境从自身路径定位，不依赖主机绝对路径或 Conda

runtime01 已通过：板端校验 6991 个文件哈希，Python/消息/rosbag2 导入成功，独立节点和组件订阅就绪、组件卸载成功、两进程正常退出 0。ldd 无缺库，进程 maps 中 OpenCV 均来自运行包 4.2，见 [运行环境证据](../infra/rk3588/reference/runtime_20261014/)。该检查没有 bag 输入，不计入完整 VIO 实验

## 板端依赖运行探针

```bash
bash infra/rk3588/scripts/prepare_legacy_smoke.sh
../.infra/bin/vins-remote firefly@10.106.0.220 ../.infra/rk3588/legacy-smoke-payload \
  --run infra/rk3588/scripts/legacy_smoke.sh --output ../results/rk3588/新的依赖探针 --timeout 90
```

准备脚本拒绝覆盖已有 payload；复用已验收 payload 时只执行第二条并指定新结果目录。源码在 infra/rk3588/probes/legacy/，检查 padded 灰度输入、八个角点的 LK 位移及输入不变，实际 SuiteSparse/CXSparse 求解均得到 x=10，25 个 ARM 动态库齐全、退出 0，见 [验收快照](../infra/rk3588/reference/legacy_20261014/)

## Profile 与时间口径

板端原先无 perf。主机从锁定包准备 ARM perf 与 11 个动态库，保留板端 glibc/loader：

```bash
bash infra/rk3588/scripts/prepare_perf.sh
../.infra/bin/vins-remote firefly@10.106.0.220 ../.infra/rk3588/perf-payload \
  --run infra/rk3588/scripts/profile_smoke.sh --output ../results/rk3588/新的采样探针 --timeout 90
```

准备脚本拒绝覆盖已有 payload。perf 实测版本 5.15.216，在厂商 5.10.110 内核上通过五类用户态事件计数、99 Hz cycles/frame-pointer 采样和函数符号解析；298 个样本、零丢样，PMU 权限保持板端原值 2，见 [profile 证据](../infra/rk3588/reference/perf_20261014/)。不替换内核，不能把测试函数热点作为 VINS 热点

Arm Streamline 可选路线需要目标 gatord，主要使用 Linux Perf API；当前已验证的 CPU 路线为 perf，[Arm 官方说明](https://github.com/ARM-software/gator)。厂商启用 DMC/DFI、sysfs 有 dmc 频率/governor，但未验证 DDR 字节/秒或 CPU 功耗计量；缺接口填不可用，不用频率、负载、cache misses 或 GPU/NPU 读数替代

板端墙上时钟未同步，远端绝对日期偏离主机。外层阶段按主机 UTC 归档，程序耗时用单调时钟，本轮未修改板端时间

## 实验与事件处理

部署需携带完整 install、运行时库和必要 ROS/Python 资源，不假定一个可执行文件足够。先核验板端动态库来源、节点/组件生命周期与回放，再按单目/双目 copy/share、组件、split ROS/memfd 去重各跑一轮，严格串行，不跑五次重复

完整回放的固定入口为 run_ros2_board_phase.py；--runtime 填已验收部署作业下运行包的绝对路径，--directory 必须为新的本机结果目录。首轮用 --upload-data 传输数据，此后省略该参数复用板端数据；每阶段均核验 bag 与运行包 SHA256，失败即停止并回收日志，不自动重跑

```bash
python3 infra/rk3588/scripts/run_ros2_board_phase.py \
  --runtime /home/firefly/vins-workspace/jobs/1791960441164-99946/ros2-payload \
  --phase baseline --prefix 新的结果前缀 --directory ../results/rk3588/新的完整回放 --upload-data
```

后续阶段为 components、pmu、shared，按桌面配置去掉重复轮次，完整输入和标定保持不变。baseline 为双目 standalone/copy/Fast DDS；components 复用该参照，增加双目 share、单目 copy/share 和双目 composed copy/share。pmu 为双目 copy/share 加计数，shared 为单目/双目 split ROS/memfd。composed/split 使用 Cyclone DDS，standalone 使用 Fast DDS，与原生阶段对应

完整阶段收回日志后在主机自动用 uv.lock/evo 评估每轮轨迹，结束通知同时包含回放与评估是否成功；资源范围以 run.json 为准，原 standalone 只统计 VINS，composed 为容器，split 分进程，不混为合计 CPU

board-components01 五轮已验收，完整证据与 gzip 日志见 [组件归档](../infra/rk3588/reference/components_20261014/)。每配置一次，未重跑旧原生批次；copy/share 轨迹有小幅差异，单轮 CPU 变化均不足 0.5%，结果与范围见第 05 份报告

板端数据只放置在 home 的 vins-workspace/datasets 下，运行包工作区增加数据指向和结果目录，已验收文件保持不变。每轮保存 telemetry.jsonl 中实际可读温度/CPU 与 dmc 频率，CPU/RSS/PSS、回放/排空及计数仍由原 runner 记录；DDR 带宽和功耗不可用

board-baseline01 发现原 SDK 缺 rmw_fastrtps_cpp，rclpy 初始化失败，VINS 尚未启动；数据与哈希已通过，失败见 [归档](../infra/rk3588/reference/baseline01_failure/)。四个补充 ARM 包单独锁定在 dependencies/locks/ros2-fastrtps.json，由同一 fetch.py 下载到独立 sysroot，不改变原 SDK。Fast DDS addon 先用 deploy_fastrtps_runtime.py 验收，再通过 --ros-addon 指定远端路径，继续完整回放时省略 --upload-data，--prefix 使用新名称

fastrtps02 已验收 Fast DDS 2.6.12 / rmw_fastrtps 6.2.10，独立节点和组件订阅/加载/卸载/退出通过，maps 中使用 addon 的 RMW 和原运行包的 OpenCV 4.2；50 个 addon 文件及 6991 个原运行文件哈希均通过，见 [证据](../infra/rk3588/reference/fastrtps_20261014/)。本机当前 --ros-addon 路径为 /home/firefly/vins-workspace/jobs/1791961492786-103062/fastrtps-payload；其他主机部署后使用自己工具输出的作业路径

保留 MH_01_easy、标定和算法参数，核验输入计数、初始化/重置、末帧、ATE/RPE、退出与共享槽位归还；报告全线程 CPU、每进程 RSS/PSS、回放/排空时间、频率/温度。排空后完成不能称实时通过，评估在主机同一 uv.lock 环境执行，结果续写第 05 份报告

VGEM 仅是桌面夹具。板端 DMA heap 若使用，需先实际验证分配、stride、缓存同步、owner 和归还，不能冒充 VGEM、真实相机或端到端零拷贝验收

大阶段由主机后台 runner 执行，结束/失败才通知一次，不在线模型轮询。积压通知按 [第 10 份账本](10_PHASE_EVENT_AUDIT.md) 去重，先统一核对当前事件、源代码和有效产物，再决定唯一下一阶段；源码与正在运行的实验产物固定，避免按旧通知反复修改
