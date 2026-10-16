# vins-remote：传输、交互终端与可恢复任务

更新日期：2026-10-16

vins-remote 2 是主机端 C++ 工具，统一提供有进度的传输、初始化后的板端终端、远端命令和实时任务日志。当前工程只在 codex/rk3588-ros1 开发；VINS 算法和 v0.1 安装包不随这次工具更新改变

## Quick Start

主机已安装工具、默认配置和用户 PATH 入口，可直接执行：

```bash

# 登录默认板端，已经切到开发目录并初始化 ROS 1 环境
vins-remote --remote
# 在板端可直接运行：roscore、vins node /绝对路径/config.yaml；exit 回主机

# 主机发送文件或目录，有整体进度，保留名称
vins-remote ./my-file --send

# 主机接收板端文件或目录，results/ 相对默认板端工作区
vins-remote results/test01 --receive --dest ./download

# 执行一个命令，实时显示输出并返回真实退出码
vins-remote --exec -- which roscore
```

默认目标是 firefly@10.106.0.220，也可以继续沿用 `vins-remote firefly@10.106.0.220 文件 ...` 的习惯。板端已经建立稳定 install 入口，日常无需重复找环境文件或版本目录

完整部署和运行使用更新后的主机工具箱，v0.1 原目录的 host/ 保留作冻结交付：

```bash
cd /home/eric/projects/releases/remote-tools/v2

# 部署一个新版本，检查通过后选为默认 install；已有同版本拒绝覆盖
python3 deploy.py /home/eric/projects/releases/ros1-v0.1/install-ros1-v0.1-linux-aarch64.tar.gz

# 当前 v0.1 已部署，直接检查即可，不要为查看进度重复部署
python3 run.py --output /home/eric/projects/results/user-remote-check01

# 完整 EuRoC 回放；自行选择新的主机结果目录
python3 run.py --bag /home/firefly/vins-workspace/datasets/euroc_20261014/MH_01_easy.bag \
  --output /home/eric/projects/results/user-remote-euroc01
```

自动任务会实时显示阶段事件和各进程的 .log；结束后收回日志。终端显示的 Remote job 和本机 remote_job.json 用于接回任务：

```bash
vins-remote /终端输出的作业绝对路径 --follow
vins-remote /终端输出的作业绝对路径 --stop
vins-remote /终端输出的作业绝对路径 --collect ./recovered
```

**Ctrl-C 退出日志查看，不停止自动任务；停止用 --stop。** SSH 断线不重新启动实验，重连后 follow/collect 同一作业。手动 --remote 中 Ctrl-C 则遵循普通 SSH 终端的前台命令行为

## 1. 固定路径与配置

| 项目 | 默认位置 |
| --- | --- |
| SSH 目标 | firefly@10.106.0.220 |
| 板端工作区 | ~/vins-workspace |
| 交互/单条命令工作目录 | ~/vins-workspace/projects/vins |
| 当前安装入口 | ~/vins-workspace/install → 已验收 releases/ros1-版本/install |
| 环境初始化 | ~/vins-workspace/install/env.sh |
| 默认上传目录 | ~/vins-workspace/incoming |
| 自动任务 | ~/vins-workspace/jobs/唯一编号 |
| 用户数据 / 现场项目 | 工作区 datasets/、projects/；实验输出放 install 外 |
| 主机工具 / 配置 | /home/eric/projects/.infra/bin/vins-remote、vins-remote.conf |
| 用户 PATH 命令入口 | ~/.local/bin/vins-remote，指向主机工具 |
| 可交付主机工具箱 | /home/eric/projects/releases/remote-tools/v2/ |

默认配置源码是 infra/remote/vins-remote.conf，首次安装时复制到可执行文件旁，升级保留已有配置。优先级为命令行覆盖 > --config 文件 > VINS_REMOTE_CONFIG 环境变量指定的文件 > 可执行文件旁的配置 > 内置默认值。文件只保存 target/root/cwd/env，不保存密码，也不执行配置内容

```bash
vins-remote --print-config
vins-remote --config /path/another.conf --remote
vins-remote user@other-board --root other-workspace --remote
vins-remote --remote --cwd /other/project --env /other/environment.sh
```

配置中的相对 root/cwd/env 及显式远端 --dest 相对 SSH 用户 home；--root 会重新派生默认 cwd/env，显式 --cwd/--env 保留。receive 的相对源路径相对工作区；绝对路径和 ~/ 保持对应含义。本地路径相对主机当前目录

稳定 install 是板端链接，不是复制或重建库。部署通过检查后才切换它；历史版本目录保持原样，若 install 是真实目录则拒绝替换。回退时先检查旧版本，再显式选择旧目录；不得随意指向旧失败 payload。配置默认值不改变镜像、网络、驱动权限或系统 ROS

## 2. 文件传输：send / receive

```bash
vins-remote user@board ./directory --send --dest vins-workspace/incoming
vins-remote user@board incoming/directory --receive --dest ./download
```

省略 --send 与旧版一样表示发送。两端采用 rsync over SSH，需已有免密 SSH、rsync；不启动 rsync daemon，不写密码。显示整体字节进度、速率等，使用 .rsync-partial 保留中断数据，再执行同一传输可利用已有部分

文件/目录都保留源名称，目录有无尾部 / 不改变这一规则；例如发送 directory 到 incoming 后是 incoming/directory，接收到 download 后是 download/directory。不要把它理解成 rsync 原生命令尾斜杠的“只复制内容”语义

普通传输允许更新目标中的同名文件，不自动删除目标额外文件；不使用 --delete 或 --inplace。传输成功不替代发布校验：deploy.py 仍核对压缩包 SHA256、包内清单、体系结构和运行闭包。SSH 或 rsync 错误会返回非零，部分文件不算部署成功

## 3. 初始化终端与单条命令

--remote 要求交互终端，使用 SSH PTY，先加载用户 bashrc，再加载选定的包内 env.sh 并切换工作目录，打印 REMOTE_READY。环境缺失时明确报错，不悄悄退回系统环境。进入后可手动开驱动、master、VINS；多个终端可分别登录

--exec 不创建交互 shell：自动初始化同样的环境和目录，实时透传 stdout/stderr，返回命令退出码。命令及参数由 `--` 分开，按独立参数传递，特殊字符不会被工具自行解释成 shell 命令

```bash
vins-remote --exec -- rosversion roslaunch
vins-remote --exec --no-env -- /usr/bin/python3 --version
vins-remote --exec -- bash -c 'printf "%s\n" "$VINS_INSTALL_ROOT"; pwd'
```

--no-env 用于普通系统命令或初始化前的调试。需要 shell 管道/变量时显式调用 bash -c。exec 和手动 remote 的前台命令不保证断网继续；需要恢复、超时和日志归档时使用托管 --run

## 4. 托管脚本任务：run / follow / stop / collect

```bash
vins-remote ./payload --run ./local-script.sh --output ./new-result --timeout 300
vins-remote ./payload --run ./local-script.sh --output ./new-result --detach
```

payload 可为文件或目录。每次创建独立作业，上传脚本和嵌入在工具中的 Python helper，脱离 SSH 会话运行；无需板端常驻服务或安装第三方 Python 包。主机输出目录必须新建，先保存作业回执，再启动；保留旧版 --run/--output/--timeout 调用

脚本当前目录仍为作业目录，以保持旧实验兼容；不会预先 source ROS 环境。工具提供统一路径，脚本自行选择需要的环境，deploy.py/run.py 已自动处理：

| 变量 | 含义 |
| --- | --- |
| VINS_REMOTE_ROOT | 当前作业绝对路径 |
| VINS_REMOTE_PAYLOAD | 上传的输入文件或目录 |
| VINS_REMOTE_WORKSPACE | 默认板端工作区绝对路径 |
| VINS_REMOTE_CWD | 默认开发目录绝对路径 |
| VINS_REMOTE_ENV | 默认环境文件绝对路径 |

需要回收的文件写入 `$VINS_REMOTE_ROOT/logs/`，子目录也会回收。脚本可调用已提供的 `vins_event STEP_CODE "说明"` 报告阶段；不得根据固定 sleep 假报“节点已就绪”

--follow 重新显示该任务的已保存事件和日志，然后持续跟随；不会启动第二次。--follow --output 可在任务结束后回收。--collect 只接收已有 logs，不判断任务是否已完成；运行中收回的是部分快照，结束后可再次接收

原 --run 结果目录中有 remote_job.txt/json 回执；同一任务可以在该目录补收，其他已有目录拒绝混入。也可以使用新的本地目录。旧版作业没有 helper 时仍支持 collect，不能用新 follow/stop 管理旧作业

--stop 只向记录中身份匹配的 worker 请求停止，先 SIGINT，10 秒后 SIGTERM，15 秒后 SIGKILL；通过 /proc 起始时间核验 PID，拒绝向复用 PID 发信号。它清理拥有的脚本进程组；脚本自行创建新 session/daemon 时必须自行负责对应进程的清理，不能拿 killall 代替管理

## 5. 实时反馈、事件与退出状态

默认跟随 events.jsonl、console.log 和 logs 下逐层发现的 .log，逐行添加来源；因此可以看到 VINS、roscore、回放器自己的输出。软件自身缓冲仍会影响输出时机，长时间计算期间用 RUNNING 心跳说明进程存活，不将它解释成算法健康。Python 脚本启用无缓冲输出

| 事件 | 含义 |
| --- | --- |
| JOB_STARTED / PROCESS_STARTED | worker 和脚本已启动；不等于传感器就绪 |
| RUNNING | 脚本仍存活、已运行多久；约每 5 秒一条 |
| ARCHIVE_VERIFIED / PACKAGE_VERIFIED | 部署脚本完成对应校验 |
| UNPACK_NOTICE / UNPACK_FAILED | 成功解压的诊断摘要 / 解压失败；完整内容回收为 unpack.stderr |
| CHECK_STARTED / CHECK_PASSED | 包内生命周期检查开始/通过，子进程退出缺陷仍单列 |
| INSTALL_SELECTED | 已选定默认安装入口 |
| REPLAY_STARTED / REPLAY_FINISHED | 回放脚本开始/返回，质量结论仍看 run.json |
| CANCEL_REQUESTED / TIMEOUT | 显式取消/超时处理 |
| JOB_FINISHED / AGENT_ERROR | 托管任务结束/管理器错误 |

JSONL 包含 job、code、message、UTC、板端 monotonic_ns、事件来源 PID，结束事件保存脚本原始退出值。不同主机时间未同步时不能直接拿 UTC 差值计算延迟；VINS 输入实收/初始化健康等属于后续 v0.2+，本次不伪造这些指标

```bash
vins-remote /作业绝对路径 --follow --events-only
```

--events-only 只在 stdout 输出 JSONL，传输进度和普通日志不混入，可供后续 CLI 解析；人用默认模式即可。状态/退出文件为 result.json、exit_code，原始日志保留。进程 0 表示脚本返回成功，不替代算法质量验收；v0.1 已知 −6 仍在包内检查/实验报告中记录

| 返回码 | 解释 |
| --- | --- |
| 0 | 命令/脚本返回成功，或 collect 传输成功 |
| 2 | 常见参数/本地校验错误；远端脚本也可能原样返回 2，应结合事件区分 |
| 124 | 托管任务超时 |
| 125 | 管理器无法确认完整结束，或任务自身返回 125；看日志 |
| 130 | 显式取消、任务自身返回 130，或查看被中断；结合持久 result.json 区分 |
| 255 | SSH 连接失败，或任务自身返回 255；有持久结果时按任务退出解释 |
| 其他非零 | rsync 或远端命令/脚本的真实退出码 |

连接失败时保留作业回执，不能直接判实验失败或自动重跑。若 worker 在写结束状态前异常消失，显示 JOB_STATE_UNKNOWN，保留证据，不伪报完整成功

## 6. 构建、交付与测试

主机 Ubuntu x86_64 + C++17/CMake/OpenSSH/rsync；板端需 OpenSSH、rsync、bash、系统 /usr/bin/python3。工具是主机程序，不上传 x86 可执行文件到 ARM；只向每个作业上传内嵌 helper。源码与配置在 infra/remote/，Python 主机封装在 infra/release/

从 ROS 1 checkout 根目录构建；首次手工安装到其他主机时，可将 ../.infra/bin 加入 PATH，或在 ~/.local/bin 建立 vins-remote 命令入口：

```bash
cmake -S infra/remote -B ../.infra/build/remote-v2 \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_BUILD_TYPE=Release
cmake --build ../.infra/build/remote-v2 -j2
cmake --install ../.infra/build/remote-v2 --prefix ../.infra
VINS_REMOTE_TEST_TOOL="$PWD/../.infra/bin/vins-remote" \
  python3 -m unittest discover -s infra/remote -p test_remote.py -v
python3 -m unittest discover -s infra/release -p test_workflow.py -v
```

本地集成测试使用真实 rsync 和受控本地 SSH 替身，不接触真实设备；另做真实板端的交互环境、双向传输哈希、日志提前到达、失败/取消/超时、重新跟随/回收和现有 install 无数据检查。验收证据在 infra/remote/reference/cli_v2_20261016/，不重跑历史 VIO 或将工具探针混入算法性能结果

本次工具版本独立于 VINS v0.2：通用通信和反馈先稳定，驱动/话题监控、健康检查、profile 按第 11 份指南路线图另行开发。今后用户文档均先 Quick Start 常用命令，再给详细配置、行为和恢复说明
