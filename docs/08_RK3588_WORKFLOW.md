# RK3588 本机交叉编译与远端实验

更新日期：2026-10-14

当前目标是免密 SSH、固定 scp/部署/运行/日志回收流程，在已联网的 Ubuntu 主机下载并交叉编译 ARM 产物，板端离线执行。原生桌面 52 轮已完成；本轮每种板端配置只执行一次，不重启历史重复批次、神经网络或新的算法优化

## 已确认环境与分支

目标为 `firefly@10.106.0.220`，设备树型号 Rockchip RK3588S LP4X LIXU Board；Ubuntu 22.04.5、aarch64、厂商内核 5.10.110，4 个 A55 + 4 个 A76、约 16 GiB 内存，root/home 约 95 GiB 可用。根文件系统 overlay 的 upper 位于 userdata，本轮不重启或替换系统

板端已有 GCC/CMake/Python 3.10 和系统 OpenCV 4.5.4，未发现 ROS/Ceres。sudo 非交互可用，但下载只在主机完成。ARM 依赖需独立建立，优先保留 OpenCV 4.2.0 / Ceres 1.14.0；有兼容性障碍时先保存证据，不直接混用系统 4.5.4

ROS 2 工作从原生交接 commit `7d42fac` 建立 `codex/rk3588-ros2`，保留 ros2-humble 与历史 tag。ROS 1 若需源码兼容修改，从 master 最新提交建立自己的目标分支，不合并 ROS 2 核心实现

## 免密 SSH

已生成专用 ed25519 密钥、追加板端 authorized_keys，并在主机 SSH config 仅为该 IP 配置 IdentityFile。`ssh -o BatchMode=yes firefly@10.106.0.220` 已实测成功，密码和私钥不进入工程、日志或 Git

密钥位于本机 `~/.ssh/id_ed25519_vins_rk3588`。该私钥只用于本机；其他开发机应独立生成并添加自己的公钥，不复制这台机器的私钥。公开指纹及环境证据见 [连接快照](../infra/rk3588/reference/connection_20261014/)

## scp 与运行工具

辅助工程为 `infra/remote/`，使用 C++17 和系统 OpenSSH，不实现新的 RPC 协议。当前工具面向 Linux/POSIX 主机、通过 SSH 跨 x86/ARM 架构通信；依赖 ssh、scp，远端需要 bash、setsid、timeout

```bash
cmake -S infra/remote -B ../.infra/remote-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/g++
cmake --build ../.infra/remote-build -j4
cmake --install ../.infra/remote-build --prefix ../.infra
```

默认传文件或目录到用户 home 的 vins-workspace/incoming，可明确指定目的目录：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 文件或目录
../.infra/bin/vins-remote firefly@10.106.0.220 install --dest vins-workspace/releases
```

一次调用上传 payload 和本地脚本，执行后自动回传日志；脚本使用 VINS_REMOTE_PAYLOAD、VINS_REMOTE_ROOT 定位输入及作业目录，把需要回收的结果放到 logs 子目录：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 install \
  --run 本地实验脚本.sh --output ../results/rk3588/新结果名 --timeout 1800
```

每次运行创建唯一远端作业目录，回传 console.log、起止 UTC、退出码及脚本写入的日志。远端失败也先回收日志，然后返回原退出码；本地结果目录拒绝覆盖。SSH 中断时远端 detached 作业继续，工具打印的 job 路径可直接回收，不重新上传或重跑：

```bash
../.infra/bin/vins-remote firefly@10.106.0.220 vins-workspace/jobs/作业名 \
  --collect ../results/rk3588/新回收名
```

文件传输明确使用 scp 的 legacy 模式以固定远端 POSIX 路径转义，ssh/scp 都启用 BatchMode，使用已有免密设置。真实板端验证已覆盖本地空格/单引号路径、远端空格路径、故意退出 7、失败后自动日志回收及不重跑回收；没有运行 VIO 来测试这个工具

## 本机交叉编译路线

普通重建先执行 `python3 infra/dependencies/fetch.py`，统一补齐锁定源码、交叉工具链和 ARM ROS 2 sysroot；目录和缓存规则见 [第 09 份说明](09_DEPENDENCIES.md)。下文两次 apt 准备是建立原始 SDK 的历史步骤，不是新 clone 的下载入口；冻结 SDK 和失败记录保留原位

当前 x86_64 install 不能部署到 ARM。本机用 aarch64 编译器和独立 sysroot 构建；目标头文件/库来自板端系统快照及主机下载的 ARM 包，主机运行的 CMake/Python/代码生成器与 ARM 库分开。保留桌面安装前缀，不在 ARM 调用只支持 x86 的 bootstrap

先用小型 ARM 可执行文件完成编译、ELF 架构/依赖审计、部署和运行，再构建 OpenCV/Ceres/cv_bridge、ROS/VINS。完整 install 与运行依赖打包传输；不假设仅一个可执行文件足够，也不把模拟器内执行称为交叉编译提速

联网下载、版本/校验锁定、构建和部署逐步固定为脚本；板端不执行在线 apt/pip/curl。ROS 2 官方旧 cross_compile 工具已停止支持，本工程使用明确的 CMake 工具链/sysroot，不引入该旧工具，[ROS 官方说明](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Cross-compilation.rst)

## Profile 能力

本机板端探针确认 CONFIG_PERF_EVENTS、CONFIG_HW_PERF_EVENTS、CONFIG_ARM_PMU 可用，armv8_pmuv3 注册；普通用户 task_clock、cycles、cache_misses 访问成功，当前 PMU 权限值为 2。系统原先未安装 perf、trace-cmd 或 gatord；现已通过主机下载的 ARM perf 验证实际计数、采样和函数符号解析，不安装或替换板端内核

```bash
bash infra/rk3588/scripts/prepare_perf.sh
../.infra/bin/vins-remote firefly@10.106.0.220 ../.infra/rk3588/perf-payload \
  --run infra/rk3588/scripts/profile_smoke.sh --output ../results/rk3588/新的采样探针 --timeout 90
```

准备脚本从统一包锁中取得实际 perf 二进制及 11 个 ARM 动态库，保留板端 glibc/loader，拒绝覆盖现有 payload。工具实测版本 5.15.216，在厂商 5.10.110 上完成五类用户态事件计数、99 Hz cycles 采样与 frame-pointer 调用栈；298 个样本、丢样为 0，热点函数 profile_work 可解析。证据见 [perf 快照](../infra/rk3588/reference/perf_20261014/) 和第 05 份报告，覆盖的是测试程序，不是 VINS 热点结论

板端墙上时钟未同步，perf 文件头/远端 start_utc 的日期偏离主机；本轮不修改板端时钟。阶段事件使用主机 UTC，程序耗时用单调时钟，避免跨机器相减绝对时间

可选 Arm Streamline 需要目标 gatord，主要使用 Linux Perf API；先验证 CPU perf，再决定是否值得引入更重的工具，不自动改内核或安装 GPU/NPU profiler，[Arm gator 官方说明](https://github.com/ARM-software/gator)

厂商内核启用了 DMC/DFI，当前 sysfs 有 dmc 频率及 governor，但没有 DDR perf PMU。频率、负载比例不能直接作为 DDR 字节/秒；继续核验厂商接口的单位、采样窗口及读写口径，证据不足时填不可用。CPU 功耗也需实际可读的板端计量接口或外部仪表，不以 GPU/NPU 读数替代

## 实验与验收

ARM 构建通过后锁定一次性实验矩阵：ROS 1 参照、ROS 2 单目/双目 copy/share、组件及 split ROS/memfd 对照去重执行；不运行五次重复。VGEM 是桌面夹具，板端若使用 DMA heap 需先独立核验实际分配、stride、缓存同步和归还，不冒充 VGEM 或真实相机全链路验收

固定 MH_01_easy、标定和算法参数；实验串行，明确回放与排空时间、全线程 CPU、每进程 RSS/PSS、频率/温度及输入/初始化/重置/末帧/退出。共享路径核验全像素/时间戳摘要与槽位归还，结果回主机用同一 uv.lock 离线评估 ATE/RPE，统一续写第 05 份报告

目前连接、工作流、统一依赖下载、交叉 GCC、ARM ROS 2 sysroot 与 perf 已验收，ARM 小程序运行通过；VINS 与板端 VIO 尚未完成。大批次交给本地执行器，仅阶段完成、失败或需要处理时通知当前聊天，不由模型在线轮询；手动 ssh 留给初期核实和必要调试

## 交叉工具链准备与失败回退

首次 Docker 准备阶段在拉取基础镜像前失败，daemon 的代理端口 7890 没有服务。本机实际代理为 7897，直连 Ubuntu 仓库也已验证；失败事件与原始日志见 [准备失败快照](../infra/rk3588/reference/cross_sdk01_failure/)。未编译 ARM 程序，相关准备 commit 8406859 已撤回，不混入成功实验

现改用主机私有目录下载/解包 Ubuntu aarch64 GCC 包与基础运行库，读取已认证的 apt 索引但不安装或修改系统包。包版本/架构/SHA256 保存，本机 x86_64 编译出 ARM ELF 后，仍通过 C++ 工具在板端验证运行和依赖；先验收编译器，再建立完整 ARM ROS sysroot

```bash
bash infra/rk3588/scripts/prepare_cross_toolchain.sh
```

默认前缀 `../.infra/rk3588/toolchain/`，板端小程序结果 `../results/rk3588/cross-smoke02/`。本机临时服务 `vins-rk-toolchain02.service` 承接阶段，事件在 `../results/rk3588/toolchain02/`，只在完成或失败通知一次。已有 ready 的工具链拒绝重新下载覆盖；后续 OpenCV/Ceres/ROS/VINS 尚未构建或验收

## ARM ROS 2 sysroot 下载

独立 `prepare_ros2_sysroot.py` 使用 Ubuntu/ROS 签名验证，下载 ARM Jammy/Humble 的运行与开发依赖闭包，不执行板端 apt、不安装本机系统包。独立 apt 索引/状态/cache 不与交叉 GCC 下载互相覆盖；同时下载 Ubuntu 的 ARM linux-tools/perf 作为待实测候选，只接受 arm64/all 包，保存版本及 SHA256，完成后 ready 前缀拒绝在线覆盖

```bash
python3 infra/rk3588/scripts/prepare_ros2_sysroot.py
```

默认前缀 `../.infra/rk3588/ros2-sdk/`，sysroot 子目录只供交叉编译。其中 apt cv_bridge/OpenCV 4.5.4 依赖不是最终 VINS 参照；后续仍重建 OpenCV 4.2.0 / Ceres 1.14.0 / cv_bridge 3.2.1 并审计链接。CMake 工具链位于 `infra/rk3588/cmake/aarch64.cmake`，主机程序和目标库查找分开

本阶段由 `vins-rk-sysroot03.service` 承接，事件在 `../results/rk3588/sysroot03/`。SDK 下载可与编译器下载独立进行，VIO 和性能实验仍严格串行；完成或失败才通知一次，不能将下载成功当作 ARM 构建或 VIO 验收

perf 候选工具从同一已认证的 Ubuntu ARM 仓库下载。厂商内核为 5.10，Ubuntu 工具版本可能为 5.15；跳过按 uname 选路径的 wrapper，只有实际计数、采样及符号解析检查通过才采用该用户态二进制，不更换板端内核

交叉准备里程碑已验收：25 个工具链包、807 个 ARM SDK 包的全部 SHA256 通过；本机 x86_64/GCC 11.4.0 编译出的 ELF64 AArch64 小程序在厂商 5.10.110 板端退出 0，指针宽度 8、动态库无缺失。证据见 [交叉 SDK 快照](../infra/rk3588/reference/cross_sdk_20261014/)，新 tag 为 milestone-rk3588-cross-sdk-v1；这仅证明工具链与 SDK 准备，不当作 VINS 验收

## ARM 固定版本视觉库构建

```bash
bash infra/rk3588/scripts/build_legacy.sh
```

使用统一下载目录及 cross_env.sh，为 ARM 安装 Eigen 3.3.9、OpenCV 4.2.0、Ceres 1.14.0，默认安装前缀 `../.infra/rk3588/legacy/`、构建目录 `../.infra/rk3588/build-legacy-sysroot/`。OpenCV 模块和关闭的第三方特性沿用原生参照，不开启新的板端算法优化；使用主机 GNU Make，默认四个编译任务，可通过 VINS_BUILD_JOBS 调整

首次配置因主机 fresh shell 没有 Ninja 而失败，未生成视觉库，证据见 [配置失败记录](../infra/rk3588/reference/legacy01_failure/)。已改用现有 Make、新建构建目录，依赖版本和原失败记录不变。后续重建由临时服务 vins-rk-legacy02.service 承接，唯一阶段目录 `../results/rk3588/legacy02/`，完成或失败才通知一次；截至提交入口时尚未验收库或 VINS

legacy02 随后在 Carotene 编译失败：OpenCV 4.2.0 使用旧参数 ipcp-unit-growth，GCC 11 已改名为 ipa-cp-unit-growth，见 [GCC 官方记录](https://gcc.gnu.org/legacy-ml/gcc-patches/2020-01/msg00425.html)。失败日志见 [兼容性证据](../infra/rk3588/reference/legacy02_failure/)。仅修正参数名，保留数值和默认 ARM Carotene，不升级 OpenCV；补丁位于 infra/rk3588/patches/，在独立源码副本应用，下载目录保持原样

下一构建阶段为 vins-rk-legacy03.service，事件在 `../results/rk3588/legacy03/`；仍须完成库构建、ARM ELF 与板端运行验收，不能将补丁应用通过称为视觉库或 VIO 通过

## ARM ROS 2 项目构建入口

视觉库验收完成后执行 `bash infra/rk3588/scripts/build_ros2_cross.sh`。脚本按 cv_bridge、camera_models、vins_estimator、loop_fusion、global_fusion 顺序直接调用 CMake，不依赖桌面 colcon 或 source ARM 环境；安装目录为 `../.infra/rk3588/ros2_ws/install/`，构建目录为其同级 build

代码生成使用主机 `/usr/bin/python3` 及 SDK 中可在主机运行的纯 Python ament/catkin 工具；Python/NumPy 头文件与 libpython 显式取 ARM SDK。已独立验证主机 Python 3.10.12、目标开发文件查找，以及编译得到 ELF64 AArch64 Python 模块，见 [Python 交叉探针](../infra/rk3588/reference/python_cross_20261014/)。此探针尚未在板端导入，也不表示 cv_bridge 或完整 ROS 2/VINS 已构建通过

legacy03 已完成 OpenCV 4.2.0，但 Ceres 配置失败，证据见 [Ceres 配置失败](../infra/rk3588/reference/legacy03_failure/)。解包 SDK 不执行 postinst，BLAS/LAPACK 的 alternatives 链接不存在；显式查找实际 blas/lapack 子目录。此 SDK 的 libspqr.so 未依赖 TBB，关闭旧 Ceres 的可选 TBB 探测，保留 OpenMP、SuiteSparse/LAPACK/CXSparse；安装后检查不允许这些参照功能静默关闭。新目录局部配置已通过，下一完整构建为 legacy04

legacy04 的库构建退出 0，但消费端链接探针失败，未接受为里程碑，见 [共享库链接失败](../infra/rk3588/reference/legacy04_link_failure/)。SDK 绝对符号链接使 libm.so 无法在主机解析，构建退回静态数学库；统一下载入口已将 36 个绝对链接改为目标 SDK 内的相对链接。另补齐目标库 rpath-link，解析间接 BLAS/LAPACK 依赖。包锁和归档哈希不变，旧视觉库前缀及失败构建保留，完整重建使用新目录，下一阶段为 legacy05

视觉库必须同时通过消费端链接和板端运行：`bash infra/rk3588/scripts/prepare_legacy_smoke.sh` 构建/打包探针，再用 C++ 工具传输并运行 `infra/rk3588/scripts/legacy_smoke.sh`。探针检查带 padding 的灰度输入、GFTT/LK 位移与输入不变，以及 SuiteSparse/CXSparse 两种实际稀疏求解；源码在 infra/rk3588/probes/legacy/，不能将 ldd 或 ELF 检查替代这些运行验收

legacy05 与 legacy-smoke01 已通过完整库构建、消费端链接及板端实际计算验收，见 [视觉库快照](../infra/rk3588/reference/legacy_20261014/)。OpenCV/Ceres/Eigen 版本固定，Ceres 启用宏与原生一致；传递依赖的版本/BLAS 实现差异及旧 SuiteSparse 说明更正在第 05 份报告明确列出。下一步执行 ARM ROS 2 项目构建，仍未运行板端 VIO

ARM ROS 2 首次配置在 typesupport 资源索引查询前停止，包实际已存在，见 [配置失败](../infra/rk3588/reference/ros2_build01_failure/)。构建脚本补上目标 AMENT_PREFIX_PATH，与 CMake 包路径一致；主机/目标 Python 和 Boost 查找已通过，不修改 VINS 核心。后续阶段为 ros2-build02，仍需完整构建及板端运行验收

ros2-build02 配置已通过，但 Humble 预编译消息导出的 INTERFACE_LINK_LIBRARIES 硬编码 libpython 绝对路径，构建误查主机根目录，见 [SDK 导出路径失败](../infra/rk3588/reference/ros2_build02_failure/)。统一解包规则在 ROS CMake 导出中仅为该路径添加 CMAKE_SYSROOT，记录前后哈希，原包/二进制不变。下一阶段为 ros2-build03，不修改 VINS 核心或伪装其他平台
