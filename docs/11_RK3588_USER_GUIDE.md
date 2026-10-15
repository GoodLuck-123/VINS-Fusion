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
