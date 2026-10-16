# 板端 check 与 run

更新日期：2026-10-16

## Quick Start

主机执行 `vins-remote --remote` 后，已经在板端默认项目目录和选定包环境中。v0.2 新增独立 Python 命令，无需输入 .py 或编译工具：

```bash
# 只检查架构；或组合检查架构、运行库、包内文件、输出目录
check --arc
check --arc --lib --sha --dir

# 检查配置、标定和 bag；输出位置与将来的运行对应
check --config --bag data/euroc/MH_01_easy.bag --dir --output runs/euroc01

# 可选：扫描每条输入消息的 header 时间戳
check --bag data/euroc/MH_01_easy.bag --timestamps

# 独立运行；使用新名称，实时显示阶段和进程日志
run --bag data/euroc/MH_01_easy.bag --name euroc01
```

这轮只做独立板端工具，不接入主机 deploy.py/run.py 的新联动，不实现不带选项的一键全检。`check` 不带检查项会显示帮助并返回 2。真实传感器模式保留 --mode sensor 接口，当前返回明确的未实现提示

**当前节点仍是原 v0.1 二进制，存在停止时 −6 的已知缺陷。** 完整回放产生轨迹后，若节点这样退出，run 返回 1、run.json 为 failed，并记录 known_issue 与各进程退出值；工具不把它当正常完成。线程退出修复不在本次独立 CLI 范围内，不宣称完整生产稳定性通过

## 1. check：按需选择，失败也继续检查其他选项

| 选项 | 检查内容 |
| --- | --- |
| --arc | 本机 ARM64、节点 ELF64/ARM64、小端与包声明的 ROS 1 架构 |
| --lib | 包内可执行文件/共享库的 DT_NEEDED 加载；报告缺失库，跳过可重定位 .o；不探测外部驱动或动态插件 |
| --sha | 必要文件进入清单、清单路径安全、逐文件 SHA256；不要求缓存文件进入清单 |
| --dir | 输出路径已有父目录可真实写入、剩余空间满足要求；临时写探针清理，不提前创建实验目录 |
| --config [YAML] | YAML 字段/类型/数值范围、相机模型和标定、分辨率、外参矩阵、话题；省略路径使用包内 EuRoC 双目配置 |
| --bag PATH | ROS 1 bag 可读/已索引、目标话题非空、类型/MD5、首尾 header 时间交集；默认使用包内双目话题或 --config |
| --timestamps | 与 --bag 合用，扫描目标话题全部 header，拒绝非正、重复、倒退时间戳并核对读取计数 |

可任意组合 --arc/--lib/--sha/--dir；一项失败不阻止独立项继续，整体返回非零。--bag 必须读取配置以确认话题，配置失败时不会假装数据检查通过。所有检查都不启动 ROS master、VINS 或回放器

```bash
check --config config/my-vio.yaml --bag data/my.bag --output runs/my-run01 --dir
check --sha --json package-check.json
check --arc --sha --json -                # stdout 只有 JSON，适合其他程序调用
check --dir --output runs/my-run01 --min-free-mb 1024
```

--json PATH 新建报告，拒绝覆盖已有文件；父目录需已存在。--output 为预期运行目录，默认目录检查使用当前项目 runs/。--min-free-mb 单位为 MiB，默认 512；这是空间门槛，不是对完整实验磁盘需求的预测

配置里的 output_path、pose_graph_save_path 在直接检查时必须为板端绝对路径；原上游示例的 ~/output 不会由 OpenCV 展开。传 --output 时按 run 的输出覆盖规则检查，无需修改发布模板。运行时会复制配置和标定，只调整副本的输出/标定文件路径，原参数和发布文件保持不变

标定支持原工程的 MEI、PINHOLE、PINHOLE_FULL、KANNALA_BRANDT、SCARAMUZZA。验证格式、有限值、必填参数、图像尺寸和外参旋转，不证明标定精度。默认 bag 检查只读取首尾 header 样本，按图像时间 + td 与 IMU 时间比较，不能发现中间异常；完整扫描才检查所有目标话题的时间单调性。逐帧内容、实到频率与在线 IMU 覆盖留给后续版本

## 2. run：板端独立回放

```bash
run --bag data/euroc/MH_01_easy.bag --name euroc02
run --bag data/recording.bag --config config/my-vio.yaml --name project01 --rate 0.5
run --bag /绝对路径/input.bag --output /绝对路径/新结果目录 --timeout 600
```

--name 默认 run01，结果在当前目录 runs/名称；允许 1–80 个字母、数字、点、横线、下划线，首字符为字母或数字。--output 可指定另一个新目录，已有目录一律拒绝覆盖。相对数据/配置/输出路径相对当前板端目录，不相对主机

run 做自身所需的输入校验、配置准备、输出权限/空间和执行条件检查，不自动调用 check 全套选项；需要完整预检时由使用者先执行 check。它使用私有回环 ROS master、启用 use_sim_time，启动 VINS，确认该节点订阅了目标话题，再以 --clock 回放目标图像/IMU 话题。--rate 范围为 (0,1]，默认 1；默认自动选空闲 master 端口，也可 --port 指定

回放结束后等待轨迹大小稳定，并检查轨迹非空、数值有限、时间递增和末帧附近覆盖，再停止自有进程。稳定输出是实用收尾条件，不是内部队列排空证明，也不代表实时性或精度验收；ATE/RPE、长期健康和完整状态监控按后续计划实现

同一项目使用文件锁防止并发运行，运行结束或异常退出自动释放锁；不要删除 .vins-run.lock 来绕过限制。默认总超时为 bag 时长/rate + 240 秒，可 --timeout 覆盖；还分别限制 master/订阅启动等待与轨迹收尾。失败后保留已创建的结果目录，不自动重放

## 3. 日志、取消与退出

```text
runs/euroc01/
├── config/vio.yaml、cam0.yaml、cam1.yaml    实际配置与标定副本
├── vio.csv                                轨迹
├── roscore.log、vins.log、playback.log      各进程原始输出
├── ros-logs/、ros-home/                    本次私有 ROS 日志/状态
└── run.json                               状态、阶段、来源和各进程退出
```

终端实时显示阶段与各进程输出；被调用程序本身的缓冲可能造成延迟。Ctrl-C 或 SIGTERM 请求取消，run 依次停止自己启动的进程组，先 SIGINT，超时后 TERM/KILL，保留日志；不使用 killall，也不停止其他人的 ROS 进程

| 返回码 | 含义 |
| --- | --- |
| 0 | 选定检查全部通过，或回放、基础轨迹条件及所有子进程正常结束 |
| 1 | 检查/运行失败，包括原节点 −6 清理退出；看错误路径及 run.json |
| 2 | 参数错误、未选择检查项、或尚未实现的 sensor 模式 |
| 124 | run 超时，已执行自有进程清理 |
| 130 | run 被用户取消，已保留结果 |

手动 SSH 终端运行不保证断网后继续；需要断线恢复时可由既有 vins-remote 托管脚本执行，日志/环境规则见 [12](12_VINS_REMOTE.md)，本次不新增主机封装联动。不要在通信中断后盲目启动第二次实验

## 4. 真实传感器预留接口

check/run 都保留 --mode sensor，当前拒绝执行。后续需补设备型号/序列号/权限、驱动生命周期、在线话题及类型、首条消息与频率、消息时钟关系、标定映射、断流与重连策略；不会把 bag 文件检查复用成传感器健康结论。已有 --arc/--lib/--sha/--dir 和配置验证逻辑可复用

## 5. 实现与维护

工具源码在 infra/board/，打包时将 Python 实现放 scripts/cli/，可执行入口放 bin/check、bin/run；包内 env.sh 将 bin 加入 PATH，因此日常直接使用命令。基础入口使用 /usr/bin/python3 -I，避免私有 ROS Python 环境污染；bag 解析子进程使用包内 Python 3.8 和 rosbag，不安装额外依赖

从仓库根运行本机测试用 `/usr/bin/python3 -m unittest discover -s infra/board -p test_cli.py -v`，主机系统需 PyYAML；板端已由包提供。真实 bag/生命周期探针和失败证据在 infra/board/ 与对应 reference/ 中，不将环境探针记成新的算法性能对比
