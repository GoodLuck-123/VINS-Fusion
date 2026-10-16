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

现有 v0.1 从已验收 ros1-payload02 打包而来，以下为打包命令形式；已经存在的交付目录拒绝覆盖，源码变化后需先重新构建/验收，并给新包版本与新目录：

```bash
python3 infra/release/package.py --ros ros1 --version v0.1   --runtime ../.infra/rk3588/ros1-payload02 --output ../releases/ros1-v0.1
```

打包器核对运行文件清单，生成单一 install、逐文件来源、SHA256SUMS 和 tar.gz。环境入口自动定位包目录，保留板端系统 glibc/Python，不用原构建机路径替代可迁移性检查。--runtime 的默认验收清单针对已有接受包；新构建必须先独立更新验收依据，不能改版本号冒充新构建

## 3. 部署与验证

主机工具构建见 [12 第 6 节](12_VINS_REMOTE.md#6-构建交付与测试)，部署/检查/实验使用 [11](11_RK3588_USER_GUIDE.md) 的同一入口。先检查包 SHA256、动态依赖、私有 Python、节点订阅和停止结果，再做必要完整输入回归；install 只在部署检查通过后选定

修改算法、依赖或输入链路后，应保留配置/包来源、输入计数、初始化/重置、末帧、轨迹质量和进程退出；资源记录全线程 CPU、各进程 RSS/PSS、回放与排空。缺失数据填不可用，不把排空通过当实时性通过。当前原版 −6 清理缺陷仍是待修项

历史脚本 run_ros1_board_phase.py 用于冻结 EuRoC 参照的回放与主机评估，--evaluate-only 仅评估已有结果，不重复回放；不是现场项目自动适配器。完整历史步骤可从既有 tag 查阅，当前用户入口统一 run.py。板端同一时间只运行一批实验，历史失败和积压事件按路径/哈希去重，不因旧通知回退有效安装

## 4. 维护交付

源码、脚本、文档、小型验证及 SHA256 纳入本分支，完整包/数据/SDK/日志留主机产物目录；板端不维护待 push 源码。普通小迭代提交并 push，不打 tag；仅大的 vX.0 版本按用户约定打 tag，既有 tag 和已发布包不改写
