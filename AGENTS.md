# Agent 接手约定

先读 [docs/00_HANDOFF.md](docs/00_HANDOFF.md)，再按任务读取第 01、04、05 份文档；不用先通读求解器或全部历史采样文件

## 当前状态与范围

- `master` 是 ROS 1 参照，`ros2-humble` 是当前 ROS 2 主线；后续板端实现从 ROS 2 新建目标分支，保留已有分支/tag
- 实验室目标为灰度单目视惯、200 Hz IMU；默认开环 VIO。桌面 MH_01_easy 的单目/双目已验证，板端和真实相机尚未验证
- ROS Image、memfd、VGEM 在同一实现中用 runner 参数选择。VGEM 是桌面 DMA-BUF 机制验证，EuRoC 源端仍复制像素到池
- 当前 WSL 阶段结束，后续在新 Ubuntu 主机与 RK3588 开展；不要自动重启 x86 神经网络实验或历史批次

## 环境与代码

- 命令默认从 Git 仓库根目录执行。运行工作区是父目录，安装前缀、数据与完整日志在 `../.infra/`、`../data/`、`../results/`；根目录不建软链接
- 按用户后续要求，板端依赖源码/缓存/sysroot 在 `dependencies/` 下保留 Git 占位目录，下载内容忽略；统一 `python3 infra/dependencies/fetch.py` 补齐，锁定 URL/版本/SHA256，见第 09 份说明。旧冻结依赖不迁移或改写
- Python 评估用 `infra/desktop/uv.lock`；ROS/C++ 依赖独立隔离。ROS shell 与 uv shell 分开，避免系统 OpenCV、预编译 cv_bridge 或另一 ROS 前缀污染
- 保留 OpenCV 4.2.0 / Ceres 1.14.0 及原有参数建立参照。ARM 无法满足同版本依赖时，先记录兼容性证据，再单独升级与对照
- 当前 bootstrap 和原生锁只支持 Linux x86_64；不要在 ARM 运行，也不要复制安装前缀替代重建
- 最小改动，每个实验只改一个因素；源码切换后重建，再 source 对应环境，已有 install 不代表当前源码
- 图像视图只读，owner 活到最后一个使用者结束。硬件路径核验 stride、格式、缓存/fence 和归还时机，不把借用 API 当作端到端零拷贝证明

## 验证与交付

- 可复现的构建/回放/采样/评估脚本纳入 Git；一次性开发探针放 `.local-tests/`，必要探针需可重建，不能把它当作已跟踪依赖
- 按改动运行必要检查；文档整理不重跑整批 VIO，算法或传输改动需局部正确性与完整串行 A/B
- 验收输入计数、初始化/重置、末帧轨迹、ATE/RPE、进程退出及共享槽位；排空后成功不能叫实时通过
- 报告 CPU 全线程累计秒、每进程 RSS/PSS、回放和排空时间。DDR/功耗接口缺失时填不可用，不用 CPU/cache misses/复制量替代
- 结果统一续写 `docs/05_EUROC_ROS1_ROS2_COMPARISON.md`。归档小型证据和 SHA256，历史数据/冻结哈希不改写，失败证据保留且不混入成功统计
- 大批次用本地后台 runner；仅完成、失败或需处理时触发一次通知，禁止在线模型轮询。旧机器的 hook/thread ID 不迁移
- 每个目标独立提交，验收后打 annotated tag，不移动历史 tag；按用户授权 push 目标分支/tag，不把其他分支合并进 master

文档用 Markdown，新增指南沿用编号，适度分段和分点，段内正常标点、自然段末不加中文句号；目录入口变化时同步 README 和第 00 份文档
