# RK3588 ROS 1 接手入口

更新日期：2026-10-16

## Quick Start

普通用户先读 [11 用户指南](11_RK3588_USER_GUIDE.md)，远程操作读 [12 工具指南](12_VINS_REMOTE.md)。当前主机可直接执行：

```bash
vins-remote --print-config
vins-remote --remote
```

默认目标 firefly@10.106.0.220，实验目录 ~/vins-workspace/projects/vins，安装环境 ~/vins-workspace/install/env.sh；普通上传也进入实验目录

## 当前交付

仅 codex/rk3588-ros1 继续开发，核心与标定保持 ROS 1 参照 8c7c8d2 的行为。主机产物为 ../releases/ros1-v0.2/，板端版本目录为 ~/vins-workspace/releases/ros1-v0.2/install，install 链接选定该版本；完整工具箱为 ../releases/remote-tools/current/。源码、文档和工具只在主机 Git 中维护，板端只放部署文件、数据与输出

联网 x86_64 主机下载与交叉构建，板端离线运行，固定 OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、私有 Noetic/Python 3.8；不替换板端 glibc 或系统 Python。依赖见 [09](09_DEPENDENCIES.md)，构建和重新打包见 [08](08_RK3588_WORKFLOW.md)

## 工作目录约定

普通上传与 SSH/exec 工作目录统一读取 cwd 配置，默认为 projects/vins。data/、config/、runs/ 分别保存数据、配置、具名实验。run.py 默认以主机 --output 目录名作为板端任务名，也可 --name 指定；同名任务拒绝覆盖。部署仍使用 releases/，内部部署和通用任务仍可用 jobs/ 唯一编号，不要求用户逐个查找

历史 jobs、incoming、datasets 保持原位，已建立 data/euroc/MH_01_easy.bag 到原验收数据的链接，不重复复制大 bag。旧数据是链接源，不能按“旧缓存”删除；历史运行包与证据也不迁移。v0.2 已实现独立板端 check/run，见第 13 份指南；主机联动、一键全检与完整在线健康判断仍未实现

## 验证边界

已验证完整包的校验、动态库和节点订阅就绪，以及一次 EuRoC 双目完整回放。原 VINS 同步线程停止时未 join，退出 −6；当前检查只接受已知日志特征，不能称节点正常退出。真实相机、长期稳定性、实时性、回环/GNSS 与完整自动健康诊断尚未验收

RUNNING 心跳只表示脚本存活。检查退出码、原始日志和轨迹，不用一次环境检查代替算法质量验收。板端墙上时钟未同步，跨主机耗时使用单调时钟与主机阶段记录；DDR/功耗没有有效接口

新验证的小型证据与 SHA256 放相应 infra/*/reference/，完整日志在 ../results/；交付与工具验证不混入算法性能结果。核心/输入传输改变要做正确性和串行 A/B；本次目录/工具/文档整理不重跑历史 VIO

## 历史与发布

当前分支仅保留部署、实验、工具、依赖、维护与路线图文档。桌面复现、ROS 版本对比及旧迁移/硬件优化计划从当前 docs 移除，可用 `git show milestone-rk3588-remote-cli-v2:docs/05_EUROC_ROS1_ROS2_COMPARISON.md` 查阅当时记录；历史 tag 与冻结证据不改写

当前 v0.1 固定安装包，GitHub Release 只是围绕 tag 的发布说明与附件入口，本项目未宣称已上传二进制附件。按用户修正约定，每个验收完成的 v0.x 版本打 annotated tag，版本内部小迭代靠 commit 追溯。其他分支和既有 tag 保持不变

路线图统一在 [11 第 8 节](11_RK3588_USER_GUIDE.md#8-后续功能与版本计划)，不维护重复任务书

## v0.2 本轮范围

独立 Python check/run 源码在 infra/board/，用户入口见 [13 板端 CLI](13_BOARD_CLI.md)。检查按选项组合，真实传感器仅预留接口，不接入主机 deploy.py/run.py 新联动。沿用原节点二进制，−6 清理退出不掩盖，新 run 将其报告为失败；按本轮收窄后的 CLI 范围验收，不宣称原完整 v0.2 停止修复计划已完成
