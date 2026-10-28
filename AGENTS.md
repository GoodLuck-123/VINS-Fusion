# VINS 实验平台接手约定

先读 [00 接手入口](docs/00_HANDOFF.md)，设计与版本范围统一维护在 [01 平台设计](docs/01_PLATFORM_DESIGN.md)，新板子的实测边界见 [02 板端探索](docs/02_BOARD_DISCOVERY.md)

## 当前任务

- 新主线为 `codex/vins-platform`，起点为原生 VINS `be55a937a57436548ddfb1bd324bc1e9a9e828e0`；其余分支、tag 和历史产物封存为参照，不自动继续旧版 v0.3 计划
- v0.1 工具、独立 host/ARM64 构建与私有包已实现，验收见 docs/04_VALIDATION.md；日常操作以 docs/03_USER_GUIDE.md 为准
- 工程给学生户外实验与采数使用，用户至上、最小代码生产；实现前先明确当轮目的、最短操作路径和验收标准
- v0.1 只做开环 VIO，构建 `camera_models` 与 VINS 主链；不构建回环、GNSS、KITTI、RViz，也不顺手修改历史驱动问题

## 固定结构

- 一个用户入口 `./vins`，一份根目录模板 `project.example.yaml`；用户复制为 `project.yaml` 或其他名字，通过 `-c` 选择，不再要求手改多个 ROS/VINS YAML
- 算法保留原生 C++ 目录；第三方库、驱动、SDK 统一放根目录 `third_party/`，版本、来源、校验值和小补丁可追溯
- Python 环境用 uv 锁定；C++/ROS/SDK、工具链、sysroot 用独立依赖锁与隔离构建器，不能声称 uv 能管理内核、系统 ABI 或所有 C++ 库
- 下载与构建辅助环境放 `cache/`，按目标和构建指纹保留 `build/`；最终包必须在仓库内 `releases/`，输入在 `data/`，运行结果和实采数据在 `experiments/`，禁止再向仓库同级隐藏目录生成新工程产物
- 运行包携带用户态环境，不依赖板端 `/opt/ros`、旧工作区或全局 SDK；系统内核、glibc/loader、设备节点及访问权限有明确兼容性契约，激活脚本不执行 apt/pip/厂商安装程序
- 原生依赖优先维持 OpenCV 4.2.0 / Ceres 1.14.0 的可追溯参照；更新版本必须单独给出理由和验证，不混链系统库

## 板端与验收

- 当前目标为 `firefly@192.168.1.51`，已完成免密；密码、私钥不写入配置、日志或 Git
- 板子实际为 RK3588S、Ubuntu 20.04.6、glibc 2.31；Ubuntu 版本是兼容性验证条件，不是让用户部署 ROS/SDK 的理由
- 当前相机为 FLIR Blackfly S BFS-U3-31S4M-BD，格纳威 IMU 在 `/dev/ttyS7`；用户确认保留旧驱动 `imu_rate=200` 的使用习惯，实测约 100 Hz，不改设备配置、不伪造 200 Hz 证据
- 探索可使用现有 ROS/SDK；正式验收必须通过本工程运行包，不能借用探索环境当作部署完成
- 任务独立于 SSH 存活，只清理本任务拥有的进程；断网、监控失效、设备断流、算法退出要分别报告
- 话题观察、实际写包、VINS 接收与处理是不同证据；回放结束与轨迹文件稳定不等于排空或实时通过
- 核心改动按最小正确性检查及同数据串行回放验收，保留失败；验收一个版本后再打 annotated tag，不移动历史 tag

文档先 Quick Start 再详情，使用 Markdown、自然段和必要表格；新入口同步 README 与第 00 份文档，计划与实测分开表述
