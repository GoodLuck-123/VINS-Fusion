# VINS 实验平台接手入口

更新日期：2026-10-28

## Quick Start

新主线为 `codex/vins-platform`，本轮只完成重设计与板端探索，尚未实现新 CLI、新构建或新 release

```bash
cp project.example.yaml project.yaml
ssh firefly@192.168.1.51
```

第一条复制唯一用户参数模板；第二条已完成免密，可进入现有板端环境。规划中的 `./vins remote/run/deploy` 目前不能执行

## 先读什么

- [01 平台设计](01_PLATFORM_DESIGN.md)：目的、用户流程、统一配置、目录、v0.1–v0.3 范围和验收
- [02 板端探索](02_BOARD_DISCOVERY.md)：当前系统、真实硬件、工作区、短时收数和未验证事项
- [根目录配置模板](../project.example.yaml)：先覆盖开环单目 IMU 播包，后续在同一模板扩充硬件参数
- [原生 VINS 说明](90_UPSTREAM_README.md)：上游背景与引用，不是新平台的操作指南

## 已完成与下一步

| 项目 | 本轮状态 |
| --- | --- |
| 新分支与历史封存 | 从原生 `be55a93` 建立，旧分支/tag 不变；快照见探索证据 |
| 新板子 SSH | 新主机密钥经用户确认，专用公钥安装并验证免密 |
| 实际相机 | FLIR Blackfly S BFS-U3-31S4M-BD，SDK 10 张灰度图通过 |
| 格纳威 IMU | UART 校验通过，现有 ROS 驱动约 100 Hz，785 条数值有限、时间递增 |
| 配置与目录 | 移除旧场景配置，新增唯一模板；明确 releases/data/build/experiments/third_party 职责 |
| 算法与正式工具 | 未改动、未构建；下一阶段为全新平台 v0.1 |

用户已确认旧 IMU 的 `imu_rate=200` 使用习惯保留；硬件实际约 100 Hz 单独记录，不在本轮修复。旧相机/IMU 驱动疑点只登记，不展开修补

## 工程约定

只做开环 VINS 主链；主机构建、板端解包运行，不借用板端已装 ROS/SDK 作为正式依赖。Python 工具环境由 uv 锁定，C++/ROS/工具链/SDK 单独锁定；系统 ABI 和设备权限有明确兼容条件

最终包在仓库内 `releases/`，输入在 `data/`，任务结果和实采数据在 `experiments/`，中间及历史构建在 `build/`，下载和 sysroot 在 `cache/`，全部第三方源码/驱动/SDK 在 `third_party/`。旧分支遗留的本地忽略缓存保持原位，不作为新构建输入

旧 ROS 1 v0.2.1 与新平台 v0.1 是不同版本序列；旧 `−6` 修复可按需提取最小补丁，必须以新构建重新验收。旧版本结果不等于新包已验证；原生算法源码本轮保持不变，旧 benchmark 与预研不自动纳入新主线
