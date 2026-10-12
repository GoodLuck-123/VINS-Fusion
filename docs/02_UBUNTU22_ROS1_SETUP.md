# Ubuntu 22.04 / VINS-Fusion 原版参照环境

日期：2026-10-09

## 1. 目的和环境划分

本环境服务于 EuRoC 原版参照和后续 ROS 2 迁移对比。保持 VINS-Fusion 源码、算法参数和标定，先验证双目 IMU 的 VIO。当前宿主为 Ubuntu 22.04.5、WSL2、x86_64；不包含 RK3588 BSP、相机驱动或 RGA SDK

uv 管理 Python 数据检查/评估工具及其完整依赖锁；ROS 1/C++ 工具链采用工程内 micromamba 隔离环境，OpenCV/Ceres 在独立工程内前缀源码构建。uv 不是 ROS/C++ 系统依赖管理器，不用 pip/uv 的 opencv-python 代替 C++ OpenCV

`master` 保留本页的 ROS 1 参照；ROS 2 升级在独立 `ros2-humble` 分支维护。切换分支后在新终端激活对应环境并运行该分支的构建脚本，避免源码与二进制版本混淆

本环境保留实验室的 OpenCV 4.2.0、Ceres 1.14.0，但 ROS 包构建、Python、Boost、编译器及数值库与 Ubuntu 20.04 实验室环境不同。因此它是新的 Ubuntu 22.04 原版参照，不能声称与实验室二进制环境完全相同。实验室运行结果仍可作为独立参照

目录职责：

| 路径（相对运行工作区） | 职责 |
| --- | --- |
| VINS-Fusion/ | 原始个人 fork 源码，构建时不修改 |
| .infra/ros1/ | ROS Noetic、C++ 编译器和原生依赖 |
| .infra/legacy/ | OpenCV 4.2.0、Ceres 1.14.0 安装前缀 |
| .infra/bridge_ws/ | 与 OpenCV 4.2.0 重新构建的 cv_bridge |
| .infra/vins_ws/ | 原版源码的 catkin 构建工作区，src 为软链接 |
| .infra/downloads/ | 工具和源码下载缓存 |
| .infra/build/ | 原生依赖构建缓存 |
| .infra/ros-home/ | ROS 日志、运行状态 |
| VINS-Fusion/infra/desktop/.venv/ | uv 工具环境，不与 ROS Python 混用 |
| data/euroc/ | EuRoC bag 和真值 |
| results/ros1/ | 逐次实验、轨迹、日志、资源采样与评估 |

环境损坏时按锁文件重建，无需重刷 Ubuntu。不要复制已安装前缀到另一绝对路径当作可重定位备份，应在新路径重新创建依赖和构建

## 2. 固定版本与锁文件

| 组件 | 版本 |
| --- | --- |
| ROS | Noetic，RoboStack noetic 的 Python 3.11 构建 |
| OpenCV | 4.2.0，官方 tag 源码，裁剪为 VINS/cv_bridge 所需模块 |
| Ceres | 1.14.0，官方 tag 源码，启用 C++11、SuiteSparse/LAPACK |
| Eigen | 3.3.9 |
| Boost / Boost.Python | 1.86.0 |
| glog | 0.6.0 |
| SuiteSparse | 5.10.1 |
| 编译器 | conda-forge GCC/G++ 13.4.0 |
| CMake | 3.31 系列 |
| micromamba | 2.9.0 |
| 评估 Python | 宿主 CPython 3.10.12，uv 锁定依赖 |

| 文件 | 用途 |
| --- | --- |
| environment-ros1.yml | 说明原生依赖约束，维护环境时使用。 |
| ros1-linux-64.lock | 所有原生包的具体下载 URL/版本/build/哈希，重建优先使用。 |
| pyproject.toml + uv.lock | 数据和评估工具依赖，使用 uv sync --locked。 |
| baseline-assets.sha256 | 已下载源码及数据的 SHA256，重建时校验。 |
| results/ros1/native_environment.json | 实际二进制链接检查结果。 |

ROS Noetic 官方目标为 Ubuntu 20.04，已结束官方支持；这里通过隔离的 RoboStack 包在 22.04 上运行历史参照，不把 Focal apt 源混进 Jammy，也不向 /usr 或 /usr/local 安装依赖

## 3. 首次搭建

先有 Ubuntu 22.04 自带 Python 3.10，以及 curl、git、uv。无需系统 ROS、系统 OpenCV/Ceres 或系统编译器。本机已有 uv 0.12.23。新机器缺 uv 时按官方用户级安装方式安装，随后打开新终端：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Git 仓库根目录为 `VINS-Fusion/`。文档位于 `docs/`，脚本、依赖锁和小体积参照快照位于 `infra/desktop/`，均纳入版本控制。安装前缀、数据和完整日志位于仓库父目录（运行工作区），不纳入 Git；根目录不创建软链接

新机器按以下布局克隆；已有 checkout 则直接进入仓库：

```bash
mkdir -p ~/codespace/ros_ws
cd ~/codespace/ros_ws
git clone https://github.com/GoodLuck-123/VINS-Fusion.git
cd VINS-Fusion
```

须使用包含 infra 文件的版本。以下命令均在 Git 仓库根目录执行：

```bash
git switch master
bash infra/desktop/scripts/bootstrap_baseline.sh
```

必须先切回 ROS 1 源码；当前 ROS 2 分支的 package 使用 ament，不能直接调用 catkin。master 保留原先的文档文件名，切换后按该分支 README 查找，先保存所需命令并打开新终端。当前 ROS 2 的新机接手路径见 [第 00 份文档](00_HANDOFF.md)

脚本依次安装固定版本 micromamba、按 ros1-linux-64.lock 创建 ROS/C++ 环境、uv sync、下载源码和数据、校验 SHA256、构建 OpenCV/Ceres/cv_bridge/VINS。依赖均写入本工程，不运行 sudo、不修改系统包源、不写全局 bashrc

WSL 使用 Windows 代理时，先确认镜像网络与代理监听配置能让 WSL 的 curl 联网。代理变量在当前 shell 配置即可，不写入锁文件或脚本；不要提交带凭据的代理 URL。若下载失败，保留日志并重试。下载中的 .part 不作为完整文件使用

默认 4 并发构建；内存不足时使用：

```bash
VINS_BUILD_JOBS=2 bash infra/desktop/scripts/build_ros1_baseline.sh
```

已有下载/原生环境时可只重复 build 脚本，构建会增量进行。不要删除 VINS-Fusion 来重建环境。若要重新创建环境，先停止依赖该环境的进程，把旧 .infra 前缀移到备份位置，再按锁文件创建；旧结果可保留

## 4. OpenCV 隔离和核验

搭建前检查了 dpkg、/usr 和 /usr/local 常见库/头文件/CMake/pkg-config 路径，本机未发现预装 OpenCV。即便新机器有系统 OpenCV，也不应直接依赖自动搜索的结果

infra/desktop/scripts/ros1_env.sh 为 OpenCV_DIR、Ceres_DIR、CMAKE_PREFIX_PATH、LD_LIBRARY_PATH 和 PKG_CONFIG_PATH 设置工程路径；构建明确传入 OpenCV_DIR/Ceres_DIR。cv_bridge 从源码重建，禁止混用与其他 OpenCV 版本链接的预编译 cv_bridge

原工程会覆盖 CMAKE_CXX_FLAGS，丢掉 conda 初始化时加入的头文件路径；infra/desktop/scripts/native_cmake_overrides.cmake 使 CMake 显式保留包的 include 路径。原工程使用旧 CV_* 常量，infra/desktop/scripts/opencv4_legacy_compat.h 在编译时补充 OpenCV 4.2 的兼容头文件。这两项属于构建适配，不修改 VINS 源码或算法

显式关闭未使用的 G-API/ADE，避免旧 ADE 在 GCC 13 上缺失标准头文件导致重建失败；VINS 使用的 OpenCV 模块和版本保持一致

新终端中执行：

```bash
source infra/desktop/scripts/ros1_env.sh
python infra/desktop/scripts/verify_native_environment.py
```

此检查对 vins_node、loop_fusion_node、global_fusion_node、libcv_bridge.so 执行 ldd，并检查 catkin CMakeCache。OpenCV 必须来自 .infra/legacy/lib 的 .so.4.2，Ceres 必须来自同一前缀；存在 not found 或混入其他视觉库路径则失败

不要在这个 shell 中激活 .venv，不要 source /opt/ros 的其他环境，不要安装 opencv-python 到 ROS 环境。用于评估的 uv 工具应在另一个普通终端中运行

## 5. 数据准备

入口序列：EuRoC MH_01_easy，图像 752×480、mono8、双目 20 Hz，IMU 200 Hz。使用原始 /cam0/image_raw、/cam1/image_raw、/imu0 话题和时间戳，不需要实物传感器驱动

```bash
bash infra/desktop/scripts/download_baseline_assets.sh
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python infra/desktop/scripts/inspect_euroc.py \
  ../data/euroc/MH_01_easy.bag --output ../results/ros1/MH_01_easy_bag.json
```

ETH 旧官方下载地址在本次网络中连接失败，bag 使用脚本中列出的公开镜像；校验公开文件 SHA256： `57f440ccd68ec8dc8f9461269f5909656b86198bac3adfd677b1fcc7a1428fa9`

状态真值取自 OpenVINS 仓库保存的 EuRoC MH_01_easy.csv，记录下载 URL 和本地 SHA256，采用 IMU/body 状态姿态；不使用变换到左相机的真值。官方完整 ASL 数据下载可作为今后交叉核查来源。原有自采 4.4 GB bag 本次不使用、不改动

## 6. 完整实验和评估

ROS shell 中：

```bash
source infra/desktop/scripts/ros1_env.sh
python infra/desktop/scripts/run_euroc_baseline.py --rate 1 --name MH_01_easy_run1
```

脚本使用独立端口 11321 的 ROS master，开启 use_sim_time，等待 VINS 订阅就绪，再以 1 倍速完整回放图像/IMU和 /clock。已有运行结果不会被覆盖，同名目录再次运行会拒绝

实验配置复制到结果目录，只替换 output_path 和 pose_graph_save_path 为绝对路径；原仓库 YAML 中的 ~/output 不会由 C++ 自动展开，因此不能直接作为可靠结果路径。相机标定、show_track、multiple_thread、solver time、特征数量、反向光流等参数保持原版值。先不运行回环和 GNSS

普通终端中评估：

```bash
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python infra/desktop/scripts/evaluate_baseline.py \
  ../results/ros1/MH_01_easy_run1
```

必要时第二次完整回放使用新的 --name，用于初步观察参照结果波动；需要精度统计结论时增加序列和重复次数。机器忙导致输入积压时，可另做 --rate 0.5 的功能排查，但不能将减速实验当作 1 倍速通过

输出：

| 输出 | 内容 |
| --- | --- |
| vio.csv | 原程序直接写出的轨迹（纳秒时间戳、位置、wxyz 四元数、速度） |
| trajectory.tum / groundtruth.tum | 便于复用的 TUM 格式 |
| trajectory_aligned_se3.tum | 只做 SE(3) 对齐的估计轨迹 |
| evaluation.json | ATE/RPE、时间匹配率、轨迹覆盖和对齐参数 |
| trajectory.png | 轨迹和逐点位置误差图 |
| run.json | 代码版本、配置、完整回放状态、退出状态和资源摘要 |
| resource_samples.csv | 每秒 RSS 和进程 CPU ticks；不是细粒度前后端 profile |
| vins.log / playback.log / roscore.log | 原始日志 |

评估使用 evo core API，最大时间匹配差为 0.01 秒，不做尺度校正；四元数从原版 5 位小数输出恢复单位长度。RPE 为相邻估计 pose 的平移误差，不能当作固定 1 秒间隔指标。VINS 输出的是 IMU/body pose，真值使用同一物理坐标对象

## 7. 原版行为与结果解释

原版 MULTIPLE_THREAD=1 时每帧跟踪、隔帧送入后端；输出 pose 数不等于相机帧数。起始初始化阶段不输出非线性估计轨迹，也不应统计为迁移丢帧

原版 rosNodeTest.cpp 的 sync_thread 无退出/join 路径，停止节点可能 terminate/abort。脚本先检查完整回放期间节点持续运行和轨迹有效，再单独记录清理时退出码；保留这一原版缺陷供 ROS 2 生命周期修复对照，不把清理退出码掩盖为零

本次验收结果见下一节。无显示后端的 OpenCV highgui 足够本次无 GUI 回放，但本环境没有验收 RViz 或交互式相机标定工具。构建通过不等于所有四个 package 的功能实验都通过；本次运行范围为 EuRoC 双目 IMU VIO

## 8. 本次实测结果

构建、实际链接核验、两轮完整 1 倍速回放和真值评估已完成

| 实验 | poses | 匹配率 | ATE RMSE (m) | 相邻位姿平移 RPE RMSE (m) |
| --- | ---: | ---: | ---: | ---: |
| MH_01_easy_run1 | 1831 | 99.34% | 0.253458 | 0.003085 |
| MH_01_easy_run2 | 1831 | 99.34% | 0.252677 | 0.003083 |

原算法源码未修改；两轮输出均覆盖最后图像，退出清理 abort 如第 7 节所述

详细报告见 [原版参照实测报告](03_EUROC_ROS1_BASELINE.md)，小体积参照快照在 [baseline_reference/](../infra/desktop/baseline_reference/)

## 9. 官方及数据来源

- [uv](https://docs.astral.sh/uv/)
- [RoboStack](https://robostack.github.io/conda.html)
- [ROS Noetic 平台](https://github.com/ros-infrastructure/rep/blob/master/rep-0003.rst)
- [OpenCV](https://github.com/opencv/opencv/tree/4.2.0)
- [Ceres](https://github.com/ceres-solver/ceres-solver/tree/1.14.0)
- [cv_bridge](https://github.com/ros-perception/vision_opencv/tree/1.16.2)
- [EuRoC 官方入口](https://projects.asl.ethz.ch/datasets/euroc-mav/)
- [EuRoC bag 镜像](https://huggingface.co/datasets/kavehsgh/EuRoC_MAV_Dataset_Machine_Hall_Easy_01)
- [EuRoC 状态真值](https://github.com/rpng/open_vins/blob/master/ov_data/euroc_mav/MH_01_easy.csv)
