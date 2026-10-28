# v0.1 播包使用指南

## Quick Start

在主机仓库根目录操作。首次需要 Linux x86_64、Python 3.10、uv、CMake、编译器、OpenSSH、rsync、curl 与 dpkg-deb，下载过程需要主机联网；板端需要兼容的 ARM64 Linux、SSH、rsync 和系统 glibc/loader。板端不需要安装 ROS、Python 包或编译环境

```bash
cp project.example.yaml project.yaml
# 编辑 dataset.bag；有真值时同时填写 dataset.ground_truth
./vins run --host              # 首次构建主机包并验证数据
./vins run                     # 首次交叉构建，部署到板端并运行
```

默认目标是 `firefly@192.168.1.51`，需要预先配置 SSH 免密。仓库不保存密码、私钥、设备项目配置或大数据文件。当前模板只适用于 EuRoC cam0＋IMU，真实硬件在 v0.2 接入，不能直接套用模板标定

已验收版本：`vins-platform-v0.1.0`；准确包、结果和验证限制见 [04 验收记录](04_VALIDATION.md)

正常运行会显示构建/传输进度、阶段、图像与 IMU 观察频率、位姿数量与位置、输入时间进度和告警摘要；结束后回收轨迹、实际参数、状态和压缩原始日志。有真值时计算保持尺度的 ATE 和相邻匹配位姿 RPE

## 1. 日常操作

| 需求 | 命令 |
| --- | --- |
| 默认板端播包 | `./vins run` |
| 主机验证 | `./vins run --host` |
| 启动后立即返回 | `./vins run --background` |
| 查询／持续查看 | `./vins status` / `./vins status --follow` |
| 正常停止并回收 | `./vins stop` |
| 断线重连后补收 | `./vins pull` |
| 只构建 | `./vins build --target board` / `./vins build --target host` |
| 只部署并验包 | `./vins deploy` |
| 独立检查数据首帧和已装包 | `./vins check` |
| 进入板端已激活环境 | `./vins remote` |
| 使用另一配置 | `./vins -c field.yaml run` |

以上目标操作可加 `--host`。`run` 会自动复用匹配的构建、运行包与数据，不需要手动串联 build/deploy/check。每端同时只允许一个任务，重复运行会说明已有任务；任务目录按 `实验名/001`、`002` 递增

查看时按 Ctrl-C 只退出查看，任务仍在目标端运行。使用 `stop` 才会请求停止；状态会标记 `cancelled`，这不是成功完成全数据集。SSH 中断后用相同配置重新执行 status、stop 或 pull；不要再次 run 来恢复查看

## 2. 一份配置

所有相对输入和结果路径按配置文件所在目录解析。根目录模板包含板端地址/工作目录、回放数据和区间、图像/IMU 话题及单位、相机模型和标定、VINS 外参/噪声/求解参数、超时和回收策略。复制模板后修改，不编辑生成的 `vins.yaml` 或 `camera.yaml`

`paths.cache/build/releases` 固定指向本仓库对应目录；外部配置应填写这些目录的绝对路径。输入和 experiments 可独立设置。`dataset.rate` 在 `(0,1]`，默认 1；`start_s` 相对于 bag 起点，`duration_s: null` 表示完整回放。`expected_hz` 是观察参考，不修改消息时间戳、不重采样

`monitor.enabled` 默认 true；关闭只用于开销对照，不做实时输入健康检查，仍校验轨迹和退出。`monitor.refresh_s` 控制主机显示间隔；first_message_timeout_s 与 input_stall_s 分别用于首条输入及回放期间持续无输入。运行中只获取摘要，不持续传原文日志。`results.raw_logs: compressed` 在停止后打包日志；`none` 不回传原文，但仍保存在目标端。回放数据不会重复回传，raw_data 是后续实采接口的保留策略

## 3. 产物和固定工作目录

主机 `releases/board.json`、`host.json` 指向最新构建的准确包；最终目录为 `releases/v0.1.0/rk3588/<包指纹>/install/` 或 `host/<包指纹>/install/`，同目录有 tar.gz、package.json 和 SHA256SUMS。整个 install 是一个完整用户态运行包，不能只拷贝 vins_node

```text
~/vins-workspace/
  current -> releases/<包指纹>/install
  releases/<包指纹>/install/   # 不可变运行包
  incoming/                   # 传输压缩包，可续传
  data/                       # 按内容复用的 bag
  projects/vins/              # remote 进入的位置
  experiments/<实验名>/001/   # 状态、实际配置、轨迹、压缩日志
```

一般用户使用 deploy/run，自动计算目录和激活路径，不必复制长指纹。手动使用包时，在兼容目标端解压 tar.gz，执行 `source /实际路径/install/env.sh`，即可使用包内 vins_node、ROS 工具和 `vins` 任务控制。激活脚本不修改系统环境文件、不安装依赖；离开终端即可退出该环境

`./vins remote` 默认进入 projects/vins，并激活活动任务所用包及其私有 ROS master。无活动任务时激活当前包，默认 master 为本机 11311；终端不会自动启动新算法。自动回放会自己启动独立 master、节点、观察器和回放器，不需要手动开多个 SSH 终端

本地副本在 `experiments/<实验名>/<host|board>/001/`，包含 submitted project.json、生成参数、state.json、events.jsonl、bag.json、observation.json、vio.csv、logs.tar.gz、files.json、transfer.json；配置了真值还会有 evaluation.json。失败同样保留，空轨迹的评估明确标记不可用

## 4. 怎么判断当前运行

阶段依次为 starting、replaying、draining、stopping 和 completed；失败为 failed，主动停止为 cancelled。图像/IMU 频率和位置来自独立 ROS 观察器，**观察到消息不等于 VINS 已处理全部消息**；累计位姿、轨迹末帧、初始化原始日志和真实进程退出共同用于核验

completed 要求轨迹非空、数值有限、时间递增、覆盖选定图像末帧，并且清理后所有自有进程退出为 0。当前没有算法内部队列计数，轨迹稳定和末帧覆盖不声明队列已直接证明排空，也不声明实时达标。耗时区分回放与后续收尾，子进程总 CPU 为累计线程秒；直接受管进程的 CPU 是采样下界，RSS/PSS 是采样峰值。roscore 和 rosbag CLI 的后代进程未逐一采样，不能把包装进程的 RSS 当作整个进程树内存

告警保留来源、次数和最后原文；固定外参、等待初始输入等上游 WARN 不直接判算法失败。FATAL、非法输入、持续断流、节点退出、监督超时会终止任务并保留证据。数据源正常结束后进入收尾，不将结束后的无输入误报为断流

缺文件、错误配置、缺库、架构不符或空间不足会给出失败原因。先查看终端摘要，再 pull 回收状态和压缩日志；不要靠删除任务目录或全局 pkill 恢复。构建失败的详细日志在 build/host-build.log 或 board-build.log

## 5. 构建、依赖和兼容边界

首次构建会下载锁定的 ROS/工具链/基础库包到 cache，补齐 third_party 中固定版本的 OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、cv_bridge 源码，分别编译 host 和 ARM64。主机 CLI 使用 uv.lock；ROS/C++ 依赖使用 buildkit/locks，不使用系统 ROS 前缀

重新 clone 后不带下载内容，直接 run/build 会按锁补齐。下载归档先核对校验值；源码改变会生成新的构建指纹。闭源相机 SDK、硬件驱动尚未纳入 v0.1，不在此版本中要求板端安装它们

新板端运行包以 glibc 2.31 的 AArch64 用户态为基础，携带私有 Python、ROS 和 C++ 运行依赖，仅保留操作系统 glibc/loader 边界。不能据此保证任意 Linux/BSP 都兼容；不同镜像、真实设备权限、内核驱动与 SDK 兼容性仍需按版本核验

首次双目标构建需要充足磁盘空间；中间构建、打包暂存与压缩包会同时存在。空间不足时先迁移其他无关数据，或在停止构建后清理已替代的本工程缓存/构建，不删除当前运行包或任务结果。不要降低 min_free_gib 来掩盖空间不足
