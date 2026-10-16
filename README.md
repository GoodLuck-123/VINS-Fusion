# VINS-Fusion · RK3588 ROS 1

## Quick Start

本分支面向 RK3588 离线部署和日常实验。当前安装包为 v0.1；主机已安装 vins-remote、配置免密 SSH 时：

```bash
vins-remote ./my-data --send             # 发送到默认实验目录，显示进度
vins-remote --remote                     # 进入同一目录，自动加载 ROS 环境
# 板端执行 pwd、rosversion roslaunch；exit 返回主机
```

自动检查和回放在主机运行，实时显示日志并自动回收：

```bash
cd /home/eric/projects/releases/remote-tools/current
python3 run.py --output /home/eric/projects/results/install-check01
```

拿到安装包第一次使用，从 [11 用户指南](docs/11_RK3588_USER_GUIDE.md) 开始；工具首次构建与安装见 [12 远程工具指南](docs/12_VINS_REMOTE.md)

## 固定目录

板端 `~/vins-workspace/install` 指向选定安装包，`~/vins-workspace/projects/vins/` 同时是默认上传和实验目录；其中 data/ 放数据，config/ 放配置，runs/ 按实验名称保存任务及结果。安装包仍存 releases/，不与实验文件混放。目录详情、运行和恢复命令见用户指南

## 文档入口

| 文档 | 用途 |
| --- | --- |
| [00 接手入口](docs/00_HANDOFF.md) | 当前状态、开发约定和验证边界 |
| [11 用户指南](docs/11_RK3588_USER_GUIDE.md) | 安装、数据、实验、日志和版本计划 |
| [12 远程工具](docs/12_VINS_REMOTE.md) | 传输、初始化终端、实时任务与恢复 |
| [08 构建维护](docs/08_RK3588_WORKFLOW.md) | 主机交叉构建、运行包与重新打包 |
| [09 依赖下载](docs/09_DEPENDENCIES.md) | clone 后一条命令补齐锁定依赖 |

只在 codex/rk3588-ros1 开发；ROS 2、共享内存和硬件加速保留在研究分支与历史 tag。桌面复现和对比报告不再作为本生产分支用户文档，历史可从 milestone-rk3588-remote-cli-v2 等既有 tag 查阅；冻结证据保留

## 当前能力与边界

完整 ARM64 install 包可在已验证的 RK3588S Ubuntu 22.04 镜像上离线运行，无需板端安装 ROS/OpenCV/Ceres。EuRoC 双目 + IMU 回放已经验证；真实设备接入、长期稳定性、实时性和完整健康诊断仍待实施。原版 VINS 停止时存在 −6 清理退出缺陷，日志如实保留，后续 v0.2 修复验收

本项目基于 HKUST Aerial Robotics Group 的 [VINS-Fusion](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion)，作者与论文引用见 [原论文书目](support_files/paper_bib.md)。源码遵循 [GPLv3](LICENCE)，原始功能与示例可从上游或历史版本查阅
