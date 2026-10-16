# RK3588 ROS 1 构建与打包维护

更新日期：2026-10-16

## Quick Start

只运行现有包请读 [11 用户指南](11_RK3588_USER_GUIDE.md)。维护者在联网 Linux x86_64 主机、codex/rk3588-ros1 仓库根、新 bash 中执行：

```bash
python3 infra/dependencies/fetch.py
bash infra/rk3588/scripts/build_legacy.sh
bash infra/rk3588/scripts/build_ros1_cross.sh
python3 infra/rk3588/scripts/verify_ros1_cross.py --output /tmp/new-cross-check.json
```

不要 source 桌面 ROS、另一工具链或 uv 环境。下载、交叉构建都在主机进行，不在 ARM 执行 x86 bootstrap。依赖内容和离线复用见 [09](09_DEPENDENCIES.md)

## 1. 主机目录与依赖隔离

| 目录 | 用途 |
| --- | --- |
| dependencies/ | 锁定下载、源码、工具链、Noetic sysroot；Git 只保存锁与占位 |
| ../.infra/rk3588/ros1-legacy/ | ARM OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9 |
| ../.infra/rk3588/ros1_ws/devel/ | ROS 1 交叉构建输出 |
| ../.infra/rk3588/ros1-payload02/ | 已验收旧运行包来源，冻结保留 |
| ../.infra/bin/、build/remote-v2/ | 主机工具及其构建，不当作 ARM 文件上传 |
| ../releases/ | 面向使用者的完整 install 压缩包与主机工具箱 |
| ../results/ | 主机完整验证日志与实验结果 |

使用独立 Focal/Noetic/GCC 9.4 ABI。工具链仅向主机暴露编译器所需库，禁止把整个 Focal amd64 库目录放入 LD_LIBRARY_PATH。SDK 绝对链接与 CMake 导出由脚本重定位并记录审计，不执行 deb postinst，不改主机/板端系统

cv_bridge C++ 从固定源码重建，构建副本关闭可选 Python 扩展；不混入 SDK 或系统 OpenCV/cv_bridge。原工程 install 规则不完整，因此从核验过的运行文件生成部署包，不上传 SDK 和整个构建工作区

## 2. 运行包与完整 install

编译后先生成私有 Noetic/Python 3.8 运行包，使用当前构建的真实提交和新的输出目录：

```bash
python3 infra/rk3588/scripts/prepare_ros1_runtime.py   --build-commit 当前构建的提交 --output ../.infra/rk3588/ros1-payload-new
```

v0.2 沿用已验收 ros1-payload02 的节点/库，并加入独立 Python CLI，以下为打包命令形式；已经存在的交付目录拒绝覆盖，源码变化后需先重新构建/验收，并给新包版本与新目录：

```bash
python3 infra/release/package.py --ros ros1 --version v0.2   --runtime ../.infra/rk3588/ros1-payload02 --output ../releases/ros1-v0.2
```

打包器核对运行文件清单，生成单一 install、逐文件来源、SHA256SUMS 和 tar.gz。环境入口自动定位包目录，保留板端系统 glibc/Python，不用原构建机路径替代可迁移性检查。--runtime 的默认验收清单针对已有接受包；新构建必须先独立更新验收依据，不能改版本号冒充新构建

## 3. 部署与验证

主机工具构建见 [12 第 6 节](12_VINS_REMOTE.md#6-构建交付与测试)，部署/检查/实验使用 [11](11_RK3588_USER_GUIDE.md) 的同一入口。先检查包 SHA256、动态依赖、私有 Python、节点订阅和停止结果，再做必要完整输入回归；install 只在部署检查通过后选定

修改算法、依赖或输入链路后，应保留配置/包来源、输入计数、初始化/重置、末帧、轨迹质量和进程退出；资源记录全线程 CPU、各进程 RSS/PSS、回放与排空。缺失数据填不可用，不把排空通过当实时性通过。当前原版 −6 清理缺陷仍是待修项

历史脚本 run_ros1_board_phase.py 用于冻结 EuRoC 参照的回放与主机评估，--evaluate-only 仅评估已有结果，不重复回放；不是现场项目自动适配器。完整历史步骤可从既有 tag 查阅，当前用户入口统一 run.py。板端同一时间只运行一批实验，历史失败和积压事件按路径/哈希去重，不因旧通知回退有效安装

## 4. 维护交付

源码、脚本、文档、小型验证及 SHA256 纳入本分支，完整包/数据/SDK/日志留主机产物目录；板端不维护待 push 源码。普通小迭代提交并 push，不打 tag；每个验收完成的 v0.x 版本按用户约定打 tag，既有 tag 和已发布包不改写

## 5. 线程退出修补与节点/库成对交付

v0.2.1 不覆盖原编译工作区。主机仓库根、新 bash 中执行：

```bash
VINS_ROS1_WORKSPACE="$PWD/../.infra/rk3588/ros1-shutdown-ws" bash infra/rk3588/scripts/build_ros1_cross.sh
python3 infra/rk3588/scripts/verify_ros1_cross.py \
  --workspace ../.infra/rk3588/ros1-shutdown-ws --core-reference fb4ad05 \
  --output ../results/new-build-validation.json
```

停止逻辑分别位于 vins_node 和 libvins_lib.so，两者必须来自同一次核验构建；只换入口会继续加载旧后端。板端先在隔离副本验证无输入、单线程、等待 IMU，再用同一 run/输入/配置串行 A/B，核对轨迹、精度和进程退出。探针为 infra/board/shutdown_edges.py、shutdown_ab.py，各进程 /proc 采样的最后 CPU 值标为下界，RSS/PSS 分别报告，不推断 DDR/功耗或性能收益

打包必须同时提供构建与板端验收报告，记录文件 SHA256、源码提交和基包来源：

```bash
python3 infra/release/package.py --ros ros1 --version v0.2.1 \
  --runtime ../.infra/rk3588/ros1-payload02 \
  --ros1-build-validation ../results/v021/build-validation.json \
  --ros1-runtime-validation ../results/v021/accepted-runtime.json \
  --output ../releases/ros1-v0.2.1
```

该入口仅更新核验后的节点/后端库与来源记录，要求 SONAME 依赖不变；其他依赖沿用冻结包。依赖变化则停止，另做完整运行环境构建/验收；源码已变时禁止仅给旧二进制换版本号。v0.2.1 为版本内修补，不移动 v0.2 tag，也不新建补丁 tag
