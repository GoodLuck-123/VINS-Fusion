# VINS 户外实验平台

面向学生的开环单目视觉惯性实验工程：一个 `./vins` 入口、一份用户配置，主机构建私有运行包，板端解包运行并回收实验数据

**v0.1 已通过主机与 RK3588 播包验收**，版本标记为 `vins-platform-v0.1.0`。新分支 `codex/vins-platform` 从原生 VINS `be55a93` 建立；旧 ROS 1/ROS 2 分支、tag 与实验保留作参照

## Quick Start

v0.2 正在真实硬件验收，模板现在对应板上 FLIR 单目＋GNW IMU（2×2 binning、中心裁剪、IMU→Line0 硬触发），沿用旧安装标定初值

```bash
cp project.example.yaml field.yaml
./vins -c field.yaml record    # 只采集原始数据
./vins -c field.yaml run       # 真实硬件 VINS，自动部署、摘要监控与回收
```

传输和任务进展会直接显示在终端。Ctrl-C 只退出查看，任务继续；用 `./vins status --follow` 接续查看，`./vins stop` 正常停止，`./vins pull` 补收。`./vins remote` 进入已激活私有环境的板端终端

首次主机需具备 Python 3.10、uv、CMake/编译器、OpenSSH、rsync、curl 和 dpkg-deb，且有联网与足够磁盘空间；板端无需安装 ROS/Python 包或编译环境。完整操作及兼容边界见 [03 使用指南](docs/03_USER_GUIDE.md)，验收与边界见 [04 验收记录](docs/04_VALIDATION.md)

## 文件放在哪里

| 目录 / 文件 | 含义 |
| --- | --- |
| [project.example.yaml](project.example.yaml) | 唯一用户参数模板，复制后修改 |
| [third_party/](third_party/README.md) | 依赖源码、传感器适配器及私有 SDK 的可见位置 |
| [releases/](releases/README.md) | 最终 install、压缩包及文件清单 |
| [data/](data/README.md) | 输入 bag 与真值 |
| [experiments/](experiments/README.md) | 每次结果、日志、实际配置及实采原始数据 |
| [build/](build/README.md) / [cache/](cache/README.md) | 历史/中间构建与可重建辅助环境，非部署入口 |

运行数据和生成产物 Git 忽略，源码、模板、依赖锁和小型证据纳入版本控制。新工程产物不生成到仓库同级隐藏目录

## 设计与当前实测

从 [00 接手入口](docs/00_HANDOFF.md) 开始；[01 平台设计](docs/01_PLATFORM_DESIGN.md) 说明用户流程和 v0.1–v0.3 验收；[02 板端探索](docs/02_BOARD_DISCOVERY.md) 记录新板子的实际设备、工作区及短时验证

v0.1 做通信与干净回放闭环；v0.2 接真实相机/IMU；v0.3 补硬件与采数监控。当前相机已确认是 FLIR Blackfly S，IMU 实测约 100 Hz，用户要求保留历史 200 Hz 驱动配置的使用习惯；真实硬件算法和现场标定尚未验收

原生算法来自 HKUST Aerial Robotics 的 VINS-Fusion，作者、论文与上游说明保留在 [原版 README](docs/90_UPSTREAM_README.md)，许可见 [LICENCE](LICENCE)。原来的设备/场景配置与 Docker 操作入口已从新主线清理，可从原生提交恢复
