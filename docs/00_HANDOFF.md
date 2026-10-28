# VINS 实验平台接手入口

更新日期：2026-10-28

## Quick Start

新主线为 `codex/vins-platform`，v0.1 已通过主机/板端完整播包与故障验收；版本标记 `vins-platform-v0.1.0`，实现提交 `2062e82`

```bash
cp project.example.yaml field.yaml
./vins -c field.yaml record
./vins -c field.yaml run
```

v0.2 模板现对应现场真实设备，正在验收；离线回放切换 mode 并填写 dataset.bag，保留采集时的标定。查看、停止和补收用 status、stop、pull；操作细节见第 03 份指南

## 先读什么

- [01 平台设计](01_PLATFORM_DESIGN.md)：目的、用户流程、统一配置、目录、v0.1–v0.3 范围和验收
- [02 板端探索](02_BOARD_DISCOVERY.md)：当前系统、真实硬件、工作区、短时收数和未验证事项
- [03 使用指南](03_USER_GUIDE.md)：学生播包、远控、产物路径和故障处理
- [04 验收记录](04_VALIDATION.md)：本次准确包位置、指标、故障回归及证据边界
- [根目录配置模板](../project.example.yaml)：先覆盖开环单目 IMU 播包，后续在同一模板扩充硬件参数
- [05 硬件接入](05_HARDWARE_V02.md)：v0.2 来源、阶段提交及真实验收进度
- [原生 VINS 说明](90_UPSTREAM_README.md)：上游背景与引用，不是新平台的操作指南

## 已完成与下一步

| 项目 | 本轮状态 |
| --- | --- |
| 新分支与历史封存 | 从原生 `be55a93` 建立，旧分支/tag 不变；快照见探索证据 |
| 新板子 SSH | 新主机密钥经用户确认，专用公钥安装并验证免密 |
| 实际相机 | FLIR Blackfly S BFS-U3-31S4M-BD，SDK 10 张灰度图通过 |
| 格纳威 IMU | UART 校验通过，现有 ROS 驱动约 100 Hz，785 条数值有限、时间递增 |
| 配置与目录 | 移除旧场景配置，新增唯一模板；明确 releases/data/build/experiments/third_party 职责 |
| 算法与正式工具 | 统一 CLI、host/ARM64 源码构建和私有包通过；主机原生/修复轨迹 SHA256 相同，退出 −6 → 0 |

下一阶段为 v0.2：接入板上真实相机和 IMU，沿用现有任务/监控/回收，不启动旧分支计划

用户已确认旧 IMU 的 `imu_rate=200` 使用习惯保留；硬件实际约 100 Hz 单独记录，不在本轮修复。旧相机/IMU 驱动疑点只登记，不展开修补

## 工程约定

只做开环 VINS 主链；主机构建、板端解包运行，不借用板端已装 ROS/SDK 作为正式依赖。Python 工具环境由 uv 锁定，C++/ROS/工具链/SDK 单独锁定；系统 ABI 和设备权限有明确兼容条件

最终包在仓库内 `releases/`，输入在 `data/`，任务结果和实采数据在 `experiments/`，中间及历史构建在 `build/`，下载和 sysroot 在 `cache/`，全部第三方源码/驱动/SDK 在 `third_party/`。旧分支遗留的本地忽略缓存保持原位，不作为新构建输入

旧 ROS 1 v0.2.1 与新平台 v0.1 是不同版本序列；旧 `−6` 修复可按需提取最小补丁，必须以新构建重新验收。旧版本结果不等于新包已验证；算法主流程保持原生，仅修复线程退出生命周期，旧 benchmark 与预研不自动纳入新主线
