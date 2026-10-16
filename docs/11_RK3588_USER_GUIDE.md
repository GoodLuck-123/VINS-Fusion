# RK3588 普通用户部署与运行

更新日期：2026-10-16

## Quick Start

v0.2 先交付独立板端 Python check/run。主机执行：

```bash
vins-remote --remote
```

进入板端项目后执行：

```bash
check --arc --lib --sha --dir
check --config --bag data/euroc/MH_01_easy.bag --output runs/euroc01
run --bag data/euroc/MH_01_easy.bag --name euroc01
```

组合检查项、JSON、可选时间戳扫描、取消和返回码见 [13 板端 CLI](13_BOARD_CLI.md)。本轮不新增主机 deploy.py/run.py 与板端 CLI 联动；旧主机工具仍保留原行为。v0.2.1 已修复停止线程，正常回放要求所有子进程退出 0；旧 v0.2 的 −6 仍保留历史记录

## 1. 交付与环境

主机 `/home/eric/projects/releases/ros1-v0.2.1/` 包含完整 ARM64 install/、install-ros1-v0.2.1-linux-aarch64.tar.gz 和对应 .sha256。配套主机工具使用 `/home/eric/projects/releases/remote-tools/current/`，包含 vins-remote、配置、deploy.py、run.py；原 v0.1/host 和 remote-tools/v2 是冻结旧交付，日常使用 current

板端无需联网、安装 ROS/OpenCV/Ceres、pip、源码编译或 Docker。包内已有 VINS、私有 Noetic/Python 3.8、OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9 与示例标定，不替换系统 glibc/Python。仍需兼容 ARM64 Ubuntu/BSP 和 SSH、rsync、bash、tar、sha256sum、ldd、系统 Python 3；当前只验证 RK3588S / Ubuntu 22.04.5 / 厂商内核 5.10.110

主机需 Linux x86_64、Python 3、OpenSSH、rsync 和自己的免密 SSH 公钥；无需 ROS/uv shell，不在包中写密码或复制私钥。实验数据、真实相机驱动及现场标定另行准备

## 2. 板端目录：安装与实验分开

```text
~/vins-workspace/
├── install -> releases/ros1-v0.2.1/install   当前包，自动加载其 env.sh
├── releases/ros1-v0.2.1/install/             完整发布文件，保持只读使用
├── projects/vins/                         默认上传、SSH、exec 与实验目录
│   ├── data/euroc/MH_01_easy.bag           现有数据的稳定链接
│   ├── config/                           自己的配置和标定
│   ├── runs/                             每次检查/回放一个具名任务
│   │   └── euroc-stereo01/                运行对应命令后创建
│   │       ├── logs/experiment/           轨迹、配置、资源及各进程日志
│   │       ├── logs/result.json           托管退出状态
│   │       └── run-script.sh              本次请求及管理材料
│   └── my-data/                          普通上传保留源名称
└── jobs/                                 部署与通用托管任务内部记录
```

普通上传不会自动辨别文件类型并分类；发送 my-data 就落到项目下的 my-data。希望放到 data/ 时显式 --dest vins-workspace/projects/vins/data，或直接发送本地 data 目录。收回实验可用 `vins-remote projects/vins/runs/euroc-stereo01 --receive --dest ./download`；receive 的相对源路径相对工作区根，和 send 的默认目标不同

旧 incoming/、datasets/ 和旧 jobs/ 保留原位，避免破坏已验收路径。当前 data/euroc/MH_01_easy.bag 链接到旧数据，不重复占空间；不能删除链接源。install 下不放实验输入/输出，不直接修改发布文件。v0.2 已复用这些目录并实现独立检查/回放；主机联动与在线健康检查后续实施

## 3. 部署与无数据检查

新板或新版本在主机执行：

```bash
cd /home/eric/projects/releases/ros1-v0.2.1
sha256sum -c install-ros1-v0.2.1-linux-aarch64.tar.gz.sha256
python3 ../remote-tools/current/deploy.py install-ros1-v0.2.1-linux-aarch64.tar.gz \
  --output /home/eric/projects/results/deploy-ros1-v0.2.1
```

deploy.py 显示上传进度，校验压缩包、解压至 releases/ros1-版本/install、核对清单并做无数据节点检查，成功后才选择 install。相同版本拒绝覆盖，install 为真实目录也拒绝替换；当前板选择 v0.2.1；环境预检直接用板端 check，旧主机 run.py 仍是原冒烟入口。省略 --output 的部署日志仍有自动唯一编号；需要好记路径时如上明确指定

包内 bin/vins 是自动初始化环境的入口，config/ 是示例标定，runtime/ 包含私有 ROS/Python/运行库，scripts/ 是检查与回放脚本，share/provenance/、release.json、SHA256SUMS 记录包来源

Quick Start 的无数据检查回收 runtime-check/logs/validation.json、动态库映射、VINS/roscore 日志。subscriptions_ready: true 只证明订阅建立。旧版 −6 清理 abort 仅作历史兼容；v0.2.1 退出修复的验收要求 VINS/master 为 0，其他错误不忽略，环境检查不等于算法健康

## 4. 数据回放与结果

有自己的 EuRoC bag 时先传到可读目录：

```bash
vins-remote /主机路径/MH_01_easy.bag --send --dest vins-workspace/projects/vins/data/euroc
```

普通传输允许更新同名文件，保留目标额外文件；不要覆盖仍在使用或已验收的数据。Quick Start 的回放默认 EuRoC 双目 + IMU、原话题 /cam0/image_raw、/cam1/image_raw、/imu0、1 倍速，不自动适配任意 bag。脚本使用已有 install，不重复上传；只传小请求，管理私有 master/VINS/rosbag，回放后等待排空，自动收回 logs 内容

--output 的目录名默认就是板端 runs/ 下的实验名；可用 --name 指定另一个名称，允许 1–80 个字母、数字、点、横线、下划线，首字符为字母或数字。配置从同一 vins-remote.conf 读取，换板/换工作区见第 12 份指南

主机回收目录含 experiment/vins.log、playback.log、roscore.log、vio.csv、run.json、实际配置与资源。检查 success、轨迹非空与时间覆盖、初始化/重置/丢图、各进程退出；单看外层 0 或有文件不代表精度、实时性或生产稳定性。当前不自动评估 ATE/RPE 或完整健康状态

断线后任务可继续，按主机 remote_job.json 的绝对 job 路径 follow/collect；不重复启动。Ctrl-C 只离开自动日志查看，停止用 --stop，详情见 [12 第 4 节](12_VINS_REMOTE.md#4-托管脚本任务run--follow--stop--collect)

## 5. 现场配置与手动运行

在默认项目 config/ 放真实内外参、噪声、单位、时间偏移与话题配置，示例可从 $VINS_INSTALL_ROOT/config/ 复制。EuRoC 标定不能直接用于自己的相机，YAML 的 output_path、pose_graph_save_path 使用已存在可写绝对路径，不能依赖 ~ 展开

主机分别开三个终端，每个先执行 vins-remote --remote；进入板端后：

```bash
# 终端一
roscore
# 终端二：先建立自己的输出目录，并在 YAML 中设置正确路径
mkdir -p runs/my-camera01
vins node "$PWD/config/vio.yaml" > "$PWD/runs/my-camera01/vins.log" 2>&1
# 终端三：启动另行准备的设备驱动，或回放自己的数据
rosbag play /绝对路径/recording.bag
```

真实设备驱动的安装、权限与环境由项目提供。自己的 bag 若用 --clock，在 VINS 启动前先 rosparam set /use_sim_time true；真实传感器不启用仿真时间。默认板内通信，跨机器驱动需另配 ROS_MASTER_URI/ROS_IP。当前真实设备未验收，停止使用 Ctrl-C，v0.2.1 已验证线程正常收尾；先看初始化、轨迹持续输出与异常日志

## 6. 故障与恢复

缺少环境时工具会明确报错；先 --print-config 核对目标、cwd 和 env，再用 --exec --no-env 运行系统诊断。部署后缺依赖或检查失败先保留日志，不直接覆盖版本目录。磁盘不足先辨认自己的数据与输出，旧 jobs 可能仍是历史运行包或日志来源，不按时间戳批量删除

同名任务存在时用新的 --name/--output；已有任务用 --follow、--collect，不当作可覆盖缓存。多个实验默认共享 ROS 通信资源，当前仅串行使用。RUNNING 心跳是进程存活信息，不是健康结论

## 7. 维护与发布

重新构建/打包见 [08](08_RK3588_WORKFLOW.md)，依赖补齐见 [09](09_DEPENDENCIES.md)，普通用户不需要接触 .infra 或 SDK。代码/文档只在主机提交；板端数据和日志回收后留在主机结果目录

v0.1 是既有 annotated tag，固定已发布版本；GitHub Release 可给 tag 添加说明与附件。按最新约定，后续小迭代只提交，每个验收完成的 v0.x 版本打 tag，不移动旧 tag 或重写旧包；v0.2 固定独立 CLI 的首次交付；v0.2.1 修复节点/后端库退出，原包保持冻结，补丁按 commit 追溯

## 8. 后续功能与版本计划

以下是待实施计划，不是已完成能力或承诺日期。各功能可以逐次提交，沿用当前固定项目目录、环境配置和远程工具；v0.x 功能按本轮约定范围验收后打 tag，开发中间提交不打 tag

| 版本 / 状态 | 目标 | 功能范围 | 验收条件 |
| --- | --- | --- | --- |
| **v0.1 / 已发布** | 完整部署参照 | 单一 install 包、私有 ROS/运行库、固定板端路径、环境冒烟检查、EuRoC 双目回放、离线部署与日志回收 | 已在指定 RK3588 镜像验证；ROS 1 原清理 abort −6 单列，未承诺真实相机、长期稳定性或实时性 |
| **v0.2 / 本轮独立 CLI** | 启动前检查与板端运行 | check 组合架构/依赖/清单/目录/配置/bag 检查，可选全量时间戳；独立 run 管理私有 master/VINS/回放器、订阅就绪、超时/取消和日志；sensor 仅预留接口 | 独立检查与故障注入通过；完整回放可记录轨迹与真实退出。主机联动、无参数一键全检和原节点 −6 修复未纳入本轮，不称正常清理已解决 |
| **v0.2.1 / 退出修补** | 可靠停止 | 同步线程/后端线程响应停止并 join；节点和后端库成对交付 | 无输入、单线程、等待 IMU 均退出 0；完整串行 A/B 核对初始化、末帧、ATE/RPE 与所有退出，旧 v0.2 tag/包不改写 |
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
- **回归与发布**：先固定数据、模式、配置和监控级别，再比较版本；PC 与 ARM 各用本平台基线，不把跨机器差异归因于软件版本。故障注入和长期测试也验收日志完整、清理/重启、队列与内存。新验证保存小型证据与 SHA256，完整结果留主机；每次交付记录安装目录、提交、包/数据 SHA256 和已知问题，每个验收完成的 v0.x 版本打 tag；后续可用 GitHub Release 提供说明与附件

### 与预研任务的关系

硬件加速与共享传输留在独立研究分支，不阻塞正常实验、诊断和 profile 主线；当前默认 CPU/ROS 1 路径
