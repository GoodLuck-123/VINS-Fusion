# RK3588 普通用户部署与运行

更新日期：2026-10-15

本文面向拿到安装包、准备在板上跑实验的用户。默认使用原生 CPU ROS 1 v0.1、开环 VIO；memfd、VGEM、DMA heap、ROS 2 组件等仍按预研入口管理，不是本指南的默认部署路径

v0.1 固定已经验收的 ROS 1 二进制、OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9 和 EuRoC 标定，不修改算法。它是可直接部署的实验版本；双目 EuRoC 回放已验收，真实相机、长期稳定性和实时性尚未验收。原 ROS 1 节点停止时存在同步线程未 join 引发的 abort，退出码会如实记为 −6；不能把“生成了轨迹”理解为完整生产稳定性已经通过

## 1. 拿哪个包，不需要搭什么环境

当前发布目录在主机 `/home/eric/projects/releases/`，与 `.infra/` 分开：

```text
releases/
├── ros1-v0.1/                     默认部署版本
│   ├── install/                   解压后的完整板端运行目录
│   ├── install-ros1-v0.1-linux-aarch64.tar.gz
│   ├── install-ros1-v0.1-linux-aarch64.tar.gz.sha256
│   └── host/                      只在 Ubuntu x86_64 主机使用
│       ├── vins-remote             已编译的 scp/执行/回收工具
│       ├── deploy.py              部署整个包并进行环境冒烟检查
│       └── run.py                 调用已部署版本，回收运行日志
└── ros2-v0.1/                     独立的预研包，包含 Fast DDS 补充库
```

将 ros1-v0.1 整个目录交给使用者即可，不需要交付 `.infra/`、SDK、源码或交叉编译工具链。板端压缩包只含 ARM64 运行文件；`host/` 不上传到板端。包里包含 VINS、私有 ROS Noetic/Python 3.8、OpenCV/Ceres 等动态依赖和示例配置；无需在板端联网、apt 安装 ROS、pip 安装包、源码编译，也无需 Docker

板端仍需要已有的 ARM64 Ubuntu 22.04 系统、可用 BSP/glibc、SSH、bash、tar、sha256sum、ldd 等系统工具。本包在 RK3588S / Ubuntu 22.04.5 / 厂商内核 5.10.110 验证，不是任意 Linux/任意 CPU 的通用包，不替换系统 glibc 或系统 Python。传感器驱动、相机标定和实验 bag 不在安装包中

主机只需 Ubuntu x86_64、系统 Python 3 和 OpenSSH 客户端，不用 source ROS 或启动 uv 环境。免密 SSH 是前置条件，当前主机已配置 `firefly@10.106.0.220`；换主机后先配置自己的 SSH 公钥，不在安装包或脚本里写密码

## 2. 一条命令部署

在主机执行，先进入交付目录：

```bash
cd /home/eric/projects/releases/ros1-v0.1
sha256sum -c install-ros1-v0.1-linux-aarch64.tar.gz.sha256
python3 host/deploy.py firefly@10.106.0.220 install-ros1-v0.1-linux-aarch64.tar.gz
```

脚本调用已有 C++ 工具：scp 上传整个压缩包，校验 SHA256，在板端解压到固定版本目录，核对包内文件，再检查 Python 导入、动态库来源、ROS master 和 VINS 订阅就绪。日志自动回主机交付目录下新建的 `deploy-日期时间/`，无需手动再 scp 日志

默认板端位置是：

```text
/home/firefly/vins-workspace/releases/ros1-v0.1/install/
├── bin/vins                       普通用户命令入口，自动加载私有环境
├── bin/vins_node                  原 ROS 1 VIO 程序
├── config/euroc/                  原示例配置和相机标定
├── runtime/ros/                   私有 Noetic 运行资源
├── runtime/python38/              私有 Python 3.8，不影响系统 Python
├── runtime/lib/                   OpenCV/Ceres/Boost 等运行依赖
├── runtime/python/                Python 运行依赖
├── scripts/                       环境检查、参照回放脚本
├── share/provenance/               原构建来源和逐文件对应关系
├── env.sh                         手动操作时 source 的环境入口
├── release.json                   版本、体系结构、构建来源
├── SHA256SUMS                     包内文件校验
└── README.md                      本使用文档
```

不覆盖已存在的同版本 install，不移动旧 `jobs/` 下的验收包。部署失败先查看返回的日志；若 install 已落盘而环境检查失败，可以用下一节重新检查，不要盲目覆盖安装。版本升级放到新的版本目录，使用新包对应的路径；旧包保留即可回退。实验输出与自定义配置放 install 外，不直接修改发布文件

## 3. 检查环境，不回放数据

主机执行，`--output` 必须是一个尚不存在的目录：

```bash
python3 host/run.py firefly@10.106.0.220 \
  --output /home/eric/projects/results/user-ros1-check01
```

正常情况下终端显示远端 exit 0，回收目录有 `exit_code`、`console.log`、`runtime-check/logs/validation.json`、VINS/roscore 日志和动态库映射。`subscriptions_ready: true` 表示传感器订阅已建立，尚未输入数据，不证明定位正常。validation 中 VINS 的 −6 是已知原版退出缺陷，外层检查仅在日志匹配该已知情况时接受；其他失败不会忽略

## 4. 跑已经验收的 EuRoC 实验

第一次需要传 bag，可调用固定 scp 工具；当前板端已存在 MH_01_easy.bag，可直接跳过传输：

```bash
host/vins-remote firefly@10.106.0.220 /home/eric/projects/data/euroc/MH_01_easy.bag \
  --dest vins-workspace/datasets/euroc_20261014
```

工具前两个参数依次是 `用户@地址`、本地主机文件或目录；`--dest` 相对板端用户 home。此命令只传文件；已有同名文件可能被 scp 覆盖，复用当前数据时不要再次传输

然后从主机发起回放：

```bash
python3 host/run.py firefly@10.106.0.220 \
  --bag /home/firefly/vins-workspace/datasets/euroc_20261014/MH_01_easy.bag \
  --output /home/eric/projects/results/user-ros1-euroc01
```

这里只上传小请求，使用已经部署的 install。远端在唯一 jobs 子目录启动私有 ROS master、VINS 和 rosbag，回放结束等待排空、停止进程，自动收回日志。默认双目 + IMU、EuRoC 原话题 `/cam0/image_raw`、`/cam1/image_raw`、`/imu0`、1 倍速；不是任意 bag 自动适配器，也不默认开启回环/RViz/GNSS

回收目录的 `experiment/` 包含 `vins.log`、`playback.log`、`roscore.log`、`vio.csv`、实际配置、`run.json`、资源采样。确认 `run.json` 的 success、轨迹行数和末时间戳，检查一次 `Initialization finish!`、是否出现 failure detection / throw img，以及每个进程的退出码。参考 MH_01_easy 验收为 1831 个姿态；历史 ATE/RPE、末帧和已知 abort 见第 05 份报告。单看文件存在或排空成功，不证明实时、精度或生产稳定性

当前脚本不自动做 ATE/RPE，也不安装 profile 工具；精度评估仍在主机使用维护者的锁定环境。若运行中 SSH 断开，板端任务可以继续；记录终端的 Remote job 路径，待结束后只回收，不重放：

```bash
host/vins-remote firefly@10.106.0.220 vins-workspace/jobs/终端输出的任务编号 \
  --collect /home/eric/projects/results/user-ros1-recovered01
```

## 5. 现场项目和自己的传感器

EuRoC 标定不能直接用于自己的相机。先在 install 外建立 `~/vins-workspace/projects/项目名/config/` 和 `results/`，复制对应模式示例及标定后，按真实设备修改分辨率、图像/IMU 话题、相机内参、相机与 IMU 外参、时间偏差及噪声参数；`output_path` 和 `pose_graph_save_path` 写板端已存在、可写的绝对目录，不使用 YAML 中不会自动展开的 `~`

板端手动运行方式如下，每个终端都从新的 shell 开始。第一个终端：

```bash
cd /home/firefly/vins-workspace/releases/ros1-v0.1/install
bin/vins roscore
```

第二个终端启动 VIO，用项目的真实配置：

```bash
cd /home/firefly/vins-workspace/releases/ros1-v0.1/install
bin/vins node /home/firefly/vins-workspace/projects/my-project/config/vio.yaml \
  > /home/firefly/vins-workspace/projects/my-project/results/vins.log 2>&1
```

第三个终端启动设备驱动或自己 bag 的回放。驱动需要另外提供，与配置中的话题、编码和时间戳匹配；驱动也在板端时，可用 `source install/env.sh` 后启动。若驱动在另一台机器，还需单独配置 ROS_MASTER_URI、ROS_IP 和网络互通，本指南默认板内本机通信。要用 rosbag/rostopic，可通过 `bin/vins rosbag ...`、`bin/vins rostopic ...` 调用，无需安装系统 ROS

自己的 bag 若使用 `--clock` 回放，在启动 VINS 之前先执行 `bin/vins rosparam set /use_sim_time true`，再用 `bin/vins rosbag play --clock /板端绝对路径/数据.bag`；真实传感器使用墙上时间，不启用仿真时间。以上命令均在 install 目录执行，设备驱动本身的环境仍由项目提供

程序启动后先看订阅、初始化日志和持续输出的轨迹；出现重置/丢图/输出停滞就保留日志。当前版本不提供自动“运行健康”判定，也没有真实相机已验证的承诺。停止时用 Ctrl-C，已知清理 abort 仍会记录；现场稳定停止与长期运行是后续修复/验收项

## 6. ROS 2 包如何使用

ROS 2 安装包使用相同 host/deploy.py，默认目录为 `~/vins-workspace/releases/ros2-v0.1/install/`；`host/run.py --ros ros2 --output 新目录` 只做环境/节点/组件冒烟检查。它包含完整 VINS install、私有 Humble、Python 依赖、Cyclone DDS 和 Fast DDS addon，不再需要把 addon 单独传到板端

包内 `app/` 是 ROS 2 项目，`runtime/ros/` 是 Humble，`runtime/fastrtps/` 是可选 Fast DDS。默认 Cyclone DDS；需要时在新 shell 设置 `VINS_RMW=rmw_fastrtps_cpp` 后调用 `bin/vins`。ROS 2 完整实验继续使用第 08 份工作流，不支持本指南 host/run.py 的 EuRoC 一键回放参数

自带环境只解决部署依赖问题，ROS 2 的节点、组件和通信接口仍与 ROS 1 不同；是否采用由项目接口决定。目前 ROS 1 是默认交付入口，ROS 2 与共享传输保留为独立预研版本

## 7. 开发者目录与重新打包

普通用户只关注 releases、数据和结果目录。以下是主机旧 `.infra/` 的用途分类，保留作开发/复现材料，不是要全部上传的产物：

| 目录 | 用途 / 是否上板 |
| --- | --- |
| `.infra/bin/`、`remote-build/` | 主机 C++ 传输工具及其构建，不作为 ARM 程序上传 |
| `.infra/rk3588/ros1_ws/`、`ros2_ws_overlay/` | 有效项目交叉构建工作区，打包器提取运行文件 |
| `.infra/rk3588/ros1-legacy/`、`legacy/` | 固定视觉库 ARM 前缀，打包器提取动态依赖 |
| `.infra/rk3588/ros1-payload02/`、`ros2-payload/`、`fastrtps-payload/` | 历史已验收部署输入，发布包的哈希核验来源，不要求用户再分别上传 |
| `.infra/rk3588/toolchain/`、`ros2-sdk/`、`build*`、`*-probe-*`、`*-smoke-*`、`perf-payload/` | 工具链、开发中间产物和探针，不属于默认部署 |
| `.infra/rk3588/ros1-payload/`、`ros2-payload-incomplete01/`、`ros2_ws/`、`legacy_before_sysroot_links/` | 已替代或失败材料，仅追溯，不选作安装输入 |
| `.infra/` 下其余桌面 ROS/uv/build/cache/downloads 等 | x86 桌面开发/评估环境，不上传 RK3588 |
| `dependencies/` | Git 忽略的锁定源码、工具链、sysroot；一键下载见第 09 份说明 |

维护者在对应目标分支、主机仓库根执行下列命令，`--output` 必须是新目录：

```bash
# ROS 1：codex/rk3588-ros1
python3 infra/release/package.py --ros ros1 --version v0.1 \
  --runtime ../.infra/rk3588/ros1-payload02 --output ../releases/ros1-v0.1

# ROS 2：codex/rk3588-ros2
python3 infra/release/package.py --ros ros2 --version v0.1 \
  --runtime ../.infra/rk3588/ros2-payload --addon ../.infra/rk3588/fastrtps-payload \
  --output ../releases/ros2-v0.1
```

脚本核对原验收清单、所有运行文件 SHA256，复用同一二进制重排目录并生成逐文件来源、SHA256SUMS 和单一 tar.gz；不重建、不替换旧冻结包。源码或算法变化后必须重新构建/验收，不能靠改版本号把旧二进制叫作新版本。host/vins-remote 来自已编译的本机工具，可按第 08 份文档重建

`v0.1` 是 ROS 1 源码上的 annotated Git tag，用来固定这次版本。GitHub Release 是围绕 tag 发布说明和可下载附件的网页，两者可以一起用；本次先交付本地主机的包和 tag，不宣称 GitHub 已提供二进制下载。归档中保留原构建提交，包装脚本/用户文档在 v0.1 tag，可据此追溯

## 8. 后续功能与版本计划

本节是计划，不表示功能已经实现，也不预设发布日期。当前发布为 ROS 1 `v0.1`，已有完整离线 install、环境冒烟检查、EuRoC 双目回放和日志回收；通用配置检查、自动健康诊断、完整结果闭环及真实传感器接入尚未完成。ROS 2 `v0.1-ros2-research` 独立保留，后续按项目需要适配同样的用户入口和结果格式，不要求同步发布

主线先把正常实验、故障定位和 profile 做完整，再扩展真实设备。各版本可分小步实现，但达到对应验收条件后才打版本 tag；维护修复可用 `v0.1.1` 等补丁版本，当前 `v0.1` 与已发布安装包保持不变

| 版本 / 状态 | 目标 | 功能范围 | 验收条件 |
| --- | --- | --- | --- |
| **v0.1 / 已发布** | 完整部署参照 | 单一 install 包、私有 ROS/运行库、固定板端路径、环境冒烟检查、EuRoC 双目回放、scp 与日志回收 | 已在指定 RK3588 镜像验证；ROS 1 原清理 abort −6 单列，未承诺真实相机、长期稳定性或实时性 |
| **v0.2 / 计划** | 启动前检查与统一运行 | **环境**：ARM64、必要文件/共享库、输出权限与空间。**配置/数据**：兼容现有 OpenCV YAML，核对必填项、参数范围、标定、bag 路径、话题/类型及图像与 IMU 时间交集；完整时间戳扫描可选。**入口/停止**：统一 check/run，自动加载私有环境，管理 master/VINS/回放器，订阅就绪后回放；修复原同步线程清理 abort，支持正常停止和用户取消 | 缺库、缺文件和错误配置在回放前报错，包含原因与路径；正常实验一条命令运行；正常停止无 abort、无残留，取消有独立状态且保留日志 |
| **v0.3 / 计划** | 输入与进程监控 | **进程**：启动失败、异常退出、超时及联动清理。**输入**：首条/持续无消息、实收计数、频率与间隔分布，图像尺寸/编码、IMU NaN/Inf、重复/倒退时间戳。**时序/状态**：分别记录消息时间与单调时钟，核查图像时刻前后的 IMU 覆盖；区分启动、初始化、运行、暂停、数据结束与排空 | 注入缺话题、暂停、时间戳异常和节点退出，异常分类、发生时间和关联进程正确；暂停/正常结束不误报断流，异常后日志与子进程都可收尾 |
| **v0.4 / 计划** | VINS 状态与 profile | **算法**：初始化、跟踪特征数、处理队列、重置、轨迹停更/非有限值/位姿速度突变。**耗时**：跟踪、估计、求解、排队及端到端延迟的均值/P95/最大值。**资源**：各进程/线程 CPU、RSS/PSS、温度、CPU 频率；可选 perf/PMU 计数与带符号调用栈。**开销**：关闭/基础/详细三级，阈值按配置设置 | 可依据观测区分输入不足、处理积压与算法重置；频率变化及原因证据可追溯，不能确定时标未知；同配置串行 A/B 量化监控开销，满足实施前约定的 CPU、内存与延迟预算 |
| **v0.5 / 计划** | 实验结果闭环 | **结束/质量**：数据源结束后等待处理完成，检查队列/末帧/退出；校验轨迹存在、数量、时间单调、有限值和时间覆盖。**精度**：有真值时统一 ATE/RPE、时间关联、坐标系/外参与尺度诊断。**归档**：独立运行目录保存版本/包哈希、数据标识、实际配置、系统信息、轨迹、资源、异常时间段和原始日志，生成 JSON 与简短报告 | 每次运行明确区分成功、执行失败、质量异常或取消；崩溃、未初始化、末帧未覆盖、排空超时不会判为成功；两次实验可直接比较精度、回放/排空耗时与资源，失败也有完整报告 |
| **v0.6 / 计划** | 批量回归与部署验收 | **批量**：数据集列表、模式/配置组合、重复次数，串行执行，支持按记录续跑/仅补评估，保留失败。**基线**：PC/板端分别设精度和性能退化阈值。**部署**：包清单/校验/依赖闭包，兼容镜像无预装 ROS、离线运行及更换目录检查；记录线程/亲和性、调频策略、温度及监控级别 | 新包可自动完成固定数据集回归，断点恢复不重复已完成实验；运行不依赖源码目录或构建机路径，结果可追溯到具体包、数据、配置和平台 |
| **v0.7 / 计划** | 真实相机与 IMU | **接入**：为指定设备封装 SDK/ROS 驱动和 IMU 采集，统一消息。**设备/标定**：型号/序列号、权限、连接、实际采样率、内外参、单位/坐标系、噪声与时间偏移。**同步/留存**：明确时间戳来源和时钟映射，检测同步异常，支持原始录制及同入口离线回放。**恢复**：拔插、断流、重连及 VINS 继续/重置策略 | 指定硬件、驱动和系统镜像上可一条命令运行；灰度单目 + 200 Hz IMU 的目标输入、时间覆盖与长时间稳定性按约定验证，异常可定位；实采片段可离线复现，并按可用真值/参照报告精度边界 |

### 跨版本验收口径

- **状态与退出**：分别保存实验状态、质量状态和各进程退出码。用户取消、源端结束、处理完成、算法崩溃和排空超时可区分；v0.1 对已知 abort 的兼容判断不作为新版本正常退出标准，失败证据不混入成功统计
- **计数与时间**：bag records、旁路观察计数、VINS 实收和已处理数分别标明。消息时间保留原精度，单调时钟计量本机耗时；不同设备时钟未校准前不计算跨设备端到端延迟。输出数量按模式和原后端频率验收，不强求每幅图都有一条姿态
- **精度与实时性**：VIO 用保持尺度的 SE(3) 对齐，固定真值/body 坐标系、外参、关联容差、RPE 间隔和覆盖要求，尺度误差单列；无真值填不可用。实时性另按目标输入率、处理吞吐、积压和延迟预算验收，回放后排空成功不等于实时通过
- **profile 与开销**：CPU 用进程全部线程累计秒，RSS/PSS 按进程采样；源端和消费端分别记录，资源峰值不当作同时峰值相加。profile 的采样频率、事件、用户态/内核态范围、PMU 复用比例和符号版本须注明；缺权限时记录不可用，基础实验仍可运行。DDR/功耗缺接口填不可用，不用 CPU、cache misses 或复制字节替代
- **回归与发布**：先固定数据、模式、配置和监控级别，再比较版本；PC 与 ARM 各用本平台基线，不把跨机器差异归因于软件版本。故障注入和长期测试也验收日志完整、清理/重启、队列与内存。新结果续写第 05 份报告，每次发布独立安装目录、annotated tag、包/数据 SHA256 和已知问题；后续可用 GitHub Release 提供说明与附件

### 与预研任务的关系

ROS 2、memfd、VGEM、DMA heap、RGA、NEON/NPU 沿独立目标推进，具体技术约束见 [任务书](RK3588_DEPLOYMENT_TASK_BRIEF.md)；它们不阻塞正常实验/profile 主线，也不会因版本号递增自动成为默认部署。真实相机 v0.7 先保留普通 ROS Image/CPU 参照，硬件共享另行验证 stride、格式、缓存/fence、owner 和归还时机，不把共享 API 或一次 DMA-BUF 探针当作端到端零拷贝证据
