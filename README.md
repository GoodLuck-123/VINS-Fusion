# VINS 户外实验平台

面向学生的开环单目视觉惯性实验工程：一个 `./vins` 入口、一份用户配置，主机构建私有运行包，板端解包运行并回收实验数据

**当前是重设计阶段，尚无新 CLI 或新 release**。新分支 `codex/vins-platform` 从原生 VINS `be55a93` 建立；旧 ROS 1/ROS 2 分支、tag 与实验保留作参照

## Quick Start

先复制唯一配置模板；模板当前对应 EuRoC 单目 IMU，不对应板上实物标定

```bash
cp project.example.yaml project.yaml
# 编辑 project.yaml；也可另命名为 field.yaml
ssh firefly@192.168.1.51        # 已配置免密
```

v0.1 计划提供以下统一操作，**当前尚不能执行**：

```bash
./vins run                    # 自动准备、部署、板端回放、摘要监控与回收
./vins run --host             # 主机验证同一数据集
./vins remote                # 进入已激活环境的板端终端
./vins -c field.yaml run      # 使用另一个项目配置
```

## 文件放在哪里

| 目录 / 文件 | 含义 |
| --- | --- |
| [project.example.yaml](project.example.yaml) | 唯一用户参数模板，复制后修改 |
| [third_party/](third_party/README.md) | 以后所有依赖源码、驱动与 SDK 的可见位置 |
| [releases/](releases/README.md) | 最终上板 install 和压缩包；当前尚无新包 |
| [data/](data/README.md) | 输入 bag 与真值 |
| [experiments/](experiments/README.md) | 每次结果、日志、实际配置及实采原始数据 |
| [build/](build/README.md) / [cache/](cache/README.md) | 历史/中间构建与可重建辅助环境，非部署入口 |

运行数据和生成产物 Git 忽略，源码、模板、依赖锁和小型证据纳入版本控制。新工程产物不生成到仓库同级隐藏目录

## 设计与当前实测

从 [00 接手入口](docs/00_HANDOFF.md) 开始；[01 平台设计](docs/01_PLATFORM_DESIGN.md) 说明用户流程和 v0.1–v0.3 验收；[02 板端探索](docs/02_BOARD_DISCOVERY.md) 记录新板子的实际设备、工作区及短时验证

v0.1 做通信与干净回放闭环；v0.2 接真实相机/IMU；v0.3 补硬件与采数监控。当前相机已确认是 FLIR Blackfly S，IMU 实测约 100 Hz，用户要求保留历史 200 Hz 驱动配置的使用习惯；正式算法构建和现场标定尚未验收

原生算法来自 HKUST Aerial Robotics 的 VINS-Fusion，作者、论文与上游说明保留在 [原版 README](docs/90_UPSTREAM_README.md)，许可见 [LICENCE](LICENCE)。原来的设备/场景配置与 Docker 操作入口已从新主线清理，可从原生提交恢复
