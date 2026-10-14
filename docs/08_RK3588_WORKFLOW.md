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

当前 x86_64 install 不能部署到 ARM。本机用 aarch64 编译器和独立 sysroot 构建；目标头文件/库来自板端系统快照及主机下载的 ARM 包，主机运行的 CMake/Python/代码生成器与 ARM 库分开。保留桌面安装前缀，不在 ARM 调用只支持 x86 的 bootstrap

先用小型 ARM 可执行文件完成编译、ELF 架构/依赖审计、部署和运行，再构建 OpenCV/Ceres/cv_bridge、ROS/VINS。完整 install 与运行依赖打包传输；不假设仅一个可执行文件足够，也不把模拟器内执行称为交叉编译提速

联网下载、版本/校验锁定、构建和部署逐步固定为脚本；板端不执行在线 apt/pip/curl。ROS 2 官方旧 cross_compile 工具已停止支持，本工程使用明确的 CMake 工具链/sysroot，不引入该旧工具，[ROS 官方说明](https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Cross-compilation.rst)

## Profile 能力

本机板端探针确认 CONFIG_PERF_EVENTS、CONFIG_HW_PERF_EVENTS、CONFIG_ARM_PMU 可用，armv8_pmuv3 注册；普通用户 task_clock、cycles、cache_misses 访问成功，当前 PMU 权限值为 2。本板尚未安装 perf、trace-cmd 或 gatord，因此第一条路线是在主机准备 ARM perf、传到板上做实际采样和符号解析核验

可选 Arm Streamline 需要目标 gatord，主要使用 Linux Perf API；先验证 CPU perf，再决定是否值得引入更重的工具，不自动改内核或安装 GPU/NPU profiler，[Arm gator 官方说明](https://github.com/ARM-software/gator)

厂商内核启用了 DMC/DFI，当前 sysfs 有 dmc 频率及 governor，但没有 DDR perf PMU。频率、负载比例不能直接作为 DDR 字节/秒；继续核验厂商接口的单位、采样窗口及读写口径，证据不足时填不可用。CPU 功耗也需实际可读的板端计量接口或外部仪表，不以 GPU/NPU 读数替代

## 实验与验收

ARM 构建通过后锁定一次性实验矩阵：ROS 1 参照、ROS 2 单目/双目 copy/share、组件及 split ROS/memfd 对照去重执行；不运行五次重复。VGEM 是桌面夹具，板端若使用 DMA heap 需先独立核验实际分配、stride、缓存同步和归还，不冒充 VGEM 或真实相机全链路验收

固定 MH_01_easy、标定和算法参数；实验串行，明确回放与排空时间、全线程 CPU、每进程 RSS/PSS、频率/温度及输入/初始化/重置/末帧/退出。共享路径核验全像素/时间戳摘要与槽位归还，结果回主机用同一 uv.lock 离线评估 ATE/RPE，统一续写第 05 份报告

目前只完成连接、工作流与只读能力探测，尚未完成 ARM 构建或板端 VIO。大批次交给本地执行器，仅阶段完成、失败或需要处理时通知当前聊天，不由模型在线轮询；手动 ssh 留给初期核实和必要调试

## 交叉工具链准备与失败回退

首次 Docker 准备阶段在拉取基础镜像前失败，daemon 的代理端口 7890 没有服务。本机实际代理为 7897，直连 Ubuntu 仓库也已验证；失败事件与原始日志见 [准备失败快照](../infra/rk3588/reference/cross_sdk01_failure/)。未编译 ARM 程序，相关准备 commit 8406859 已撤回，不混入成功实验

现改用主机私有目录下载/解包 Ubuntu aarch64 GCC 包与基础运行库，读取已认证的 apt 索引但不安装或修改系统包。包版本/架构/SHA256 保存，本机 x86_64 编译出 ARM ELF 后，仍通过 C++ 工具在板端验证运行和依赖；先验收编译器，再建立完整 ARM ROS sysroot

```bash
bash infra/rk3588/scripts/prepare_cross_toolchain.sh
```

默认前缀 `../.infra/rk3588/toolchain/`，板端小程序结果 `../results/rk3588/cross-smoke02/`。本机临时服务 `vins-rk-toolchain02.service` 承接阶段，事件在 `../results/rk3588/toolchain02/`，只在完成或失败通知一次。已有 ready 的工具链拒绝重新下载覆盖；后续 OpenCV/Ceres/ROS/VINS 尚未构建或验收
