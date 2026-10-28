# 使用指南

## Quick Start

在主机仓库根目录复制唯一模板。当前模板对应板上的 FLIR 单目＋GNW IMU，保留 IMU→相机 Line0 硬触发、2×2 合并与旧安装标定初值。v0.2 正在真机验收；已验收的 v0.1 播包记录见第 04 份文档

```bash
cp project.example.yaml field.yaml
./vins -c field.yaml record      # 只采集，默认60秒，结束后回收原始bag
./vins -c field.yaml run         # 同时运行 VINS，实时显示频率、位姿及告警
```

修改 `run.name` 区分实验，`run.duration_s` 控制采集时长。先检查标定与设备参数，保持视野有纹理；VINS 初始化需要适当平移与转动，静止录包成功不等于定位成功

```bash
./vins -c field.yaml status --follow   # 断线后继续查看
./vins -c field.yaml stop              # 正常收尾、关闭录包并回收
./vins -c field.yaml pull              # 补收；on_request策略可加 --raw
./vins -c field.yaml remote            # 进入已激活包和任务 master 的 SSH 终端
```

查看时 Ctrl-C 仅退出显示，板端任务继续。一般用户不需要手动 source ROS、启动 master、启动各驱动或复制 install 中的单个文件

## 1. 环境与文件位置

首次主机需要 Linux x86_64、Python 3.10、uv、CMake、编译器、OpenSSH、rsync、curl 与 dpkg-deb；下载需要主机联网。默认板端 `firefly@192.168.1.51`，需已配置免密 SSH；兼容 ARM64 Linux、glibc/loader、USB/UART 内核设备与权限是运行条件

主机交叉构建并携带私有 Python、ROS、C++ 库和 Spinnaker 用户态 SDK。板端只解包，不执行 apt/pip、厂商安装脚本，也不借用 `/opt/ros`、`/opt/spinnaker` 或旧 devel 环境。SDK 归档须先放入 `cache/archives`，来源及 SHA256 见第 05 份文档；闭源 SDK 不能从 Git clone 中取得

最终交付是 `releases/v0.2.0/rk3588/<包指纹>/install/` 及同目录 tar.gz、SHA256SUMS；最新准确路径在 `releases/board.json`。host 包在同版本的 host 下。`build/` 是中间构建，`cache/` 是可重建环境，不能拿它们上板

```text
~/vins-workspace/
  current -> releases/<包指纹>/install
  releases/<包指纹>/install/     # 完整私有包
  incoming/                     # 部署压缩包，可续传
  data/                         # 回放输入，按内容复用
  projects/vins/                # remote 默认进入的位置
  experiments/<实验名>/001/     # 实际配置、状态、轨迹、日志
    raw/capture_*.bag           # 实采原图、处理图、IMU与原始时间信息
```

主机结果在 `experiments/<实验名>/board/001/`，主机回放则为 host。任务编号递增，不以时间戳命名。手动使用完整包时 `source /实际路径/install/env.sh` 即可进入私有环境；自动流程始终使用本任务提交时选定的包，部署新包不替换运行中任务

## 2. 相机参数：只改这一份配置

`inputs.camera.device` 是 SDK 的受控入口，启动时通过 GenICam 写入相机，不是修改另一份厂商配置文件

| 参数 | 选项与用途 |
| --- | --- |
| serial | 设备序列号，默认 `25162247`，避免多相机时选错 |
| binning | `1` 不合并、`2` 为 2×2；默认 2，改变后核对标定 |
| crop | 合并后原图上的 `[x,y,width,height]`；默认 `[256,128,512,512]` 中心裁剪 |
| trigger | `hardware`：IMU→Line0；`software`：SDK 定时触发；`continuous`：自由运行 |
| fps | 仅控制 software/continuous；hardware 的脉冲频率由 IMU 硬件决定 |
| exposure.mode | `auto` 自动曝光、`manual` 固定曝光 |
| exposure.time_us | manual 的曝光时长，微秒 |
| exposure.auto_max_us | auto 的曝光上限，微秒；默认 20000，限制运动拖影 |

其余策略固定：Mono8、增益 0、Gamma 关闭、黑电平 0、无 decimation、零硬件 offset。固定采样区域为未合并时 2048×1536、2×2 时 1024×768；原始记录是这一相机输出，不是传感器全部物理像素。VINS 图像由配置裁剪后变成 `inputs.camera.width/height`；改几何、换镜头后不能继续把旧内参当作有效标定

`calibration`、`vins.body_T_cam0`、噪声与时间偏移仍在同一模板中。`body_T_cam0` 是相机→IMU，平移单位 m；`max_solver_time`、`td` 单位秒。硬触发确认了物理采样关系，但不代表 ROS 接收时间已经精确标定：Header 为接收/解析时间，相机设备时间与帧号另录 metadata，GNW 原始串口块也保留

GNW 使用 `/dev/ttyS7`、115200。`nominal_hz=200` 保留旧参数习惯，不发送改频命令；实际约100Hz，`expected_hz` 只作观察参考，不重写时间戳、不重采样

## 3. 录包、运行与离线重放

`record` 仅采集，不要求 VINS 初始化；`run` 在 `sensor` 模式下采集同时运行 VINS。录包器订阅就绪后才启动源端，结束时先停止相机，再保留末帧后的 IMU，等待算法收尾并关闭 bag。正常完成会检查实际 bag 中的消息、维度、有限值、时间和原图/处理图/metadata 数量，失败文件同样保留

`recording.split_mib` 控制分卷，原始数据在任务的 raw 子目录。`results.raw_data=always` 自动回收；`on_request` 暂不下载大 bag，需要时 `pull --raw`。回传可续传，并按清单验证；`transfer.json` 记录本次是否包含 raw

同一段实采数据重放：在该配置的副本中只切换下列字段，保留这次采集的图像/IMU 话题与标定

```yaml
run:
  mode: replay
  name: field-replay
# 其他 run 字段保留
dataset:
  bag: experiments/field-vio/board/001/raw  # 单个.bag或含分卷的目录
  rate: 1.0
  start_s: 0
  duration_s: null
  ground_truth: null
```

```bash
./vins -c replay.yaml run --host   # 主机验证同段采集数据
./vins -c replay.yaml run          # 板端回放，不启动真实设备
```

路径相对于所选配置文件。不要把 EuRoC 标定套到现场设备；也不要把现场模板直接用于 EuRoC。旧 EuRoC 用户配置可继续使用，v0.1 tag 中保留当时的模板；测试专用 EuRoC fixture 不是另一份用户配置入口

## 4. 状态和成功的含义

阶段为 starting → capturing/replaying → draining → stopping → completed；异常为 failed。主动终止回放为 cancelled；传感器采集在进入 capturing 后可用 stop 提前结束并按真实产物验收，启动阶段取消仍为 cancelled

终端显示输入频率、位姿数量/位置及 WARN/ERROR 聚合；原始日志不持续全量回传，停止后压缩归档。ROS 观察数不等于 VINS 实收/处理数；录包实际数量独立检查，初始化、非空有限轨迹、末帧覆盖及进程退出共同判定 VINS 流程成功。无真值实采不声明绝对精度，也不以轨迹稳定声明内部队列直接排空或实时达标

监督器仅清理本任务进程组。首帧超时、持续断流、非法输入、节点退出、FATAL、监督超时分别保留原因；正常源结束后不误报断流。缺库、缺文件、权限、空间不足应明确给出路径；详细构建日志在 `build/board-build.log` 或 host-build.log，运行日志在本次任务的 logs.tar.gz

## 5. 开发和排查入口

`build --target board/host` 只构建，`deploy` 只推送验包，`check` 检查当前配置与已部署包；硬件完整连通性在采集启动时核验，check 不改相机状态。`run/record --background` 提交后返回。每端只允许一个活动任务；重复 run 不用于重连，使用 status

`remote` 激活当前包；有任务时也选择它的私有 master，没有任务时默认 11311。进入终端不自动启动节点。包内 `vins` 控制入口仍可直接使用，日常建议由主机 `./vins` 管理配置与回收

源码和依赖锁纳入 Git；SDK/下载源码/缓存、构建、包和大数据忽略。源码改变产生新指纹，SDK 或驱动变更不再迫使重编整套 OpenCV/Ceres。历史包和失败证据保留，未经完整验收不打版本 tag
