# 接手与迁移

更新日期：2026-10-12

## 1. 先确认当前状态

本页是另一台电脑或 agent 的接手入口。当前 `ros2-humble` 回到共享传输 benchmark 完成后的实现，保留编号文档；功能参照 tag 为 `milestone-ros2-shared-repeats-v1`，本轮整理不改变 VIO/传输代码和实验数据。`master` 保留 ROS 1，分支与七个历史 tag 已推送

本轮交接快照为 `milestone-ros2-desktop-handoff-v1`，标识入口整理与现有证据核验完成，不表示 ARM/新机器验收完成

实验室目标是工业相机灰度单目 + 200 Hz IMU、开环 VIO。下一步在新的 Ubuntu 主机与 RK3588 建立真实环境；当前 WSL 阶段结束。硬件加速和神经网络方向待板端重新验证，当前仓库没有神经网络实验环境或实现

| 范围 | 已知状态 |
| --- | --- |
| ROS 1 / ROS 2 | Ubuntu 22.04 WSL x86_64 的隔离构建与完整 EuRoC 对照完成 |
| 单目/双目 | MH_01_easy 全图像/IMU、轨迹末帧覆盖与真值评估通过；ROS 2 正常退出 |
| 组件与只读视图 | 独立入口和组件共存；一个进程只允许一个 VINS 估计器 |
| 三种传输 | 同一代码通过参数选 ROS Image / memfd / VGEM，30 次串行重复已归档 |
| RK3588 / 相机 | BSP、ARM 依赖、实际驱动、缓存/fence、NPU 和功耗未验收 |
| 其他功能 | 回环、GNSS、KITTI、RViz 未完成数据验收；历史 ROS 1 Docker/硬件 launch 未迁移 |

共享路径源端内存下降，双目 memfd 在本机有 CPU 收益；单目 CPU 收益未确定，VGEM CPU 更高且双目背压减速。默认保留普通 ROS Image，不能据桌面结果预测板端性能。完整结论读 [第 05 份报告末节](05_EUROC_ROS1_ROS2_COMPARISON.md#shared-repeats)，候选优化读 [第 06 份文档](06_X86_CPU_EXPERIMENTS.md)，后者尚未实施

## 2. 仓库与运行工作区

```text
ros_ws/                           # 任意可写父目录，不能与其他 checkout 共用运行前缀
├── VINS-Fusion/                   # Git 仓库；下文命令从这里执行
│   ├── AGENTS.md                  # agent 的工作约定
│   ├── docs/                     # 00 接手、01 设计、02–04 搭建、05 结果、06 候选
│   ├── vins_estimator/           # VIO、ROS 2 节点/组件、EuRoC 源和共享缓冲
│   ├── camera_models/            # 相机模型和标定工具
│   ├── loop_fusion/ global_fusion/ # 未完整验收的扩展模块
│   ├── config/ ros2/             # 传感器 YAML 与 ROS 2 公共适配
│   └── infra/desktop/            # 脚本、原生锁、uv.lock 和实验归档
├── .infra/                       # 独立 ROS 1/2 与 OpenCV/Ceres、构建和下载缓存
├── data/euroc/                   # bag、转换后的 rosbag2、IMU/body 真值
└── results/                      # 原始日志和每轮采样，不入 Git
```

脚本从自身位置解析仓库和父工作区；新机器保持单独父目录，ROS 1 历史脚本按约定使用仓库名 `VINS-Fusion`。完整日志、数据和安装前缀不随 clone 迁移，已提交的 `infra/desktop/` 文件约 24 MiB。归档 JSON 中的旧绝对路径是历史来源，不能当作新机器运行路径，不应改写

`infra/desktop/baseline_reference/` 是最初 ROS 1 参照，`ros2_reference/` 是最小迁移对照，`comparison_reference/` 保存组件、PMU、共享缓冲、DMA-BUF 和 30 轮重复实验。各目录有 `SHA256SUMS`；早期六份清单中的路径相对 `infra/desktop/`，30 轮清单相对批次目录，不改写历史清单

例如从仓库根目录核验 ROS 1 与 30 轮归档：

```bash
(cd infra/desktop && sha256sum --check baseline_reference/SHA256SUMS)
(cd infra/desktop/comparison_reference/shared_repeats_20261010 && sha256sum --check SHA256SUMS)
```

## 3. 新 Ubuntu x86_64 主机的最短路径

以下是已验证桌面构建的复现路径，要求 Ubuntu 22.04、系统 Python 3.10、curl、git、uv 和可用下载网络。uv 的首次安装见 [第 02 份文档](02_UBUNTU22_ROS1_SETUP.md#3-首次搭建)。不需要系统 ROS 或系统 OpenCV/Ceres

```bash
mkdir -p ~/codespace/ros_ws
cd ~/codespace/ros_ws
git clone --branch ros2-humble https://github.com/GoodLuck-123/VINS-Fusion.git
cd VINS-Fusion
git status --short --branch
uname -m
VINS_BUILD_JOBS=2 bash infra/desktop/scripts/bootstrap_ros2.sh
```

bootstrap 按 linux-64 锁创建原生环境，按 uv.lock 建立评估环境，下载并校验数据/源码，构建 OpenCV/Ceres/cv_bridge/VINS，并转换和逐消息校验 bag。代理仅在当前 shell 配置，不复制旧机器的 Windows 代理地址或凭据。不要把系统 `/opt/ros` 环境叠加到本工程

随后在新 ROS 2 终端中核验并跑一次目标单目参照；`--name` 使用未存在的名称：

```bash
cd ~/codespace/ros_ws/VINS-Fusion
source infra/desktop/scripts/ros2_env.sh
python infra/desktop/scripts/verify_ros2_environment.py
python infra/desktop/scripts/run_ros2_euroc.py \
  --name MH01_mono_newhost_01 --mode mono_imu \
  --deployment standalone --image-mode share --image-transport ros --rate 1
```

在另一个普通终端评估，保持 ROS Python 和 uv Python 分开：

```bash
cd ~/codespace/ros_ws/VINS-Fusion
UV_CACHE_DIR="$PWD/../.infra/uv-cache" uv run --project infra/desktop --locked python \
  infra/desktop/scripts/evaluate_baseline.py ../results/ros2/MH01_mono_newhost_01
```

检查 run.json/evaluation.json 与日志：3682 帧左图、单目右图 0、36820 条 IMU，末帧覆盖、初始化/重置、正常退出和精度。已有完整参照通常输出 1831 poses、1819 个真值匹配；求解器按墙钟预算运行，精度数值不要求逐位相等。回放和排空时间分开记录，完整成功不直接等于 20 Hz 实时

ROS 1 对照前先检查工作区干净、`git switch master`，再开新终端，使用该分支的 `bootstrap_baseline.sh` / `ros1_env.sh`。master 文档保留旧文件名，按其 README 查找；不能对当前 ROS 2 package 调用 catkin。切回 ROS 2 后重新构建并 source，tag/branch 切换不会切换现有二进制

## 4. 已跟踪的操作入口

| 目的 | 入口（相对仓库根目录） |
| --- | --- |
| ROS 2 完整重建 / 增量构建 | `infra/desktop/scripts/bootstrap_ros2.sh` / `build_ros2.sh` |
| ROS 2 同版本原生依赖重建 | `infra/desktop/scripts/build_ros2_native.sh` |
| 激活 / 真实链接核验 | `infra/desktop/scripts/ros2_env.sh` / `verify_ros2_environment.py` |
| bag 转换 / 全传感器字段校验 | `infra/desktop/scripts/convert_euroc_ros2.sh` |
| 一轮 VIO / CPU、内存采样 | `infra/desktop/scripts/run_ros2_euroc.py` |
| 轨迹评估 | `infra/desktop/scripts/evaluate_baseline.py`，普通 uv 终端 |
| 实验续写 / 小型归档 | `infra/desktop/scripts/append_euroc_comparison.py` |
| 历史三路径 30 轮方案 | `infra/desktop/scripts/run_shared_repeats.py`，普通系统 Python |
| DDR/功耗/PMU 能力清单 | `infra/desktop/scripts/probe_hardware_metrics.py` |

run_ros2_euroc.py 的 `--deployment` 可选 standalone（独立 VINS + ros2 bag）、component（容器 VINS + ros2 bag）、composed（同进程源 + VINS）和 split（独立源 + VINS）。`--image-mode copy/share` 控制图像入口，`--image-transport ros/memfd/vgem/dma_heap` 控制源到 VINS 的路径；共享后端要求 split + share

memfd 是普通 CPU 共享像素；VGEM 是软件 DRM 分配器导出的真实 DMA-BUF。EuRoC 两者都在解包后复制一次到缓冲池，再通过 SCM_RIGHTS 注册 fd，逐帧发送元数据。它们是两个可选分配后端；memfd 不是 DMA-BUF 句柄传递方式。当前原型仅单生产者/单消费者、同机线性灰度，不支持热重连或多消费者

组件和 split 的本机对照使用 Cyclone DDS；`cyclonedds_wsl.xml` 是已验证的 WSL 小分片配置，新主机先验证默认传输，再决定是否沿用。三路径重复 runner 固定该 XML 和 `/dev/dri/card0`，没有自动选设备或 resume；它是历史复现入口，不应直接当作板端 runner。VGEM 设备必须先核实驱动和权限，DMA heap 本机未验证

`.local-tests/` 的临时探针、通知 hook 和 thread ID 不随 clone 迁移，也不是正式 runner 的必需依赖。新实验需要通知时，在新机器创建自己的终止 hook；当前仓库不安装定时任务或全局服务

## 5. RK3588 的下一步

先记录板型/BSP、系统版本、内核、架构、相机接口/SDK、图像格式/stride、硬件时间戳与 IMU 同步；RKNN、RGA 等组件还要记录 SDK/runtime/驱动版本。这些信息未锁定，当前没有可直接执行的 ARM bootstrap 或平台锁

ARM 前缀单独建立，uv 继续管理 Python 工具，ROS/C++ 从目标平台重新求解或源码构建；优先保持 Humble、OpenCV 4.2.0、Ceres 1.14.0。若旧依赖无法满足目标平台，保留错误证据，将升级作为单独变量，不复制 x86 安装前缀或直接混用系统 OpenCV

先在板端以普通 ROS Image 跑相同 EuRoC 输入和单目配置，建立板端 CPU/内存/温控参照，再对接真实相机 + IMU。确认时间同步和完整性后，分别立项 DMA-BUF/RGA、NEON 或 NPU 推理，测局部和完整 VIO；每次只增加一个变量。需要改相机 SDK/驱动时先确认缓冲导出能力，VGEM 成功不代表相机 DMA 或缓存/fence 已验证

结果继续追加第 05 份报告，标明新机器、输入和采样口径。CPU/RSS/PSS、DDR、功耗分别报告；缺少硬件接口填不可用。每个目标独立分支/提交，验收后打 annotated tag，保留失败证据与既有归档；详细范围和估算见 [第 01 份任务书](01_RK3588_DEPLOYMENT_PLAN.md)

交接核验：本轮检查文档本地链接/锚点、Python 与 shell 语法、两份 bootstrap 的 ARM 拒绝路径和 runner 参数/30 轮 dry-run；七份归档共 602 个 SHA256 条目通过。现有 ROS 2 动态库/构建路径隔离核验通过，核心实现和实验表格未改。未重新跑 VIO 或在新机器从零构建；新主机与板端仍按本页步骤实测验收
