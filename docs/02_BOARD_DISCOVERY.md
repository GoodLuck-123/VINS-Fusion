# 新 RK3588 板端探索

取证日期：2026-10-28，主机日期；板端时钟停在 2026-09-22，未进行校时

## Quick Start

```bash
ssh firefly@192.168.1.51
```

免密已验证。**当前能进入的是板子的既有环境，新平台还没有安装**；不要将 `source /opt/ros/noetic/setup.bash` 作为以后普通用户的使用步骤

本轮确认相机 SDK 可以实际成像、格纳威 IMU 可以实际输出。正式的私有包、开环 VINS 构建和真实传感器 VIO 仍未验收；功能范围统一见 [01 平台设计](01_PLATFORM_DESIGN.md)

## 1. 本轮结果

| 对象 | 当前证据 | 结论边界 |
| --- | --- | --- |
| SSH | 专用公钥安装；普通 BatchMode SSH 成功 | 新板子密钥不同已由用户确认，没有覆盖其他 IP 的信任 |
| 相机 | Spinnaker 枚举 1 台 FLIR，取得并解码 10 张灰度图 | USB/SDK/短时成像通过，未测稳定帧率、触发或同步 |
| IMU 串口 | 5.026 秒约 27 KB，499 个完整校验帧，全部有限 | 帧头 55 d1 00 02 与 GNW500 解析格式匹配；设备精确型号待核实 |
| IMU ROS | 8 秒窗口观察到 785 条，约 100.001 Hz | 观察数不是 VINS 实收；200 是旧驱动配置值，不是实测输出 |
| 清理 | 自有 IMU/master 均退出 0，串口恢复原设置 | 未留下 ROS/驱动/SDK 探针进程 |
| 新平台 | 分支、模板、文档完成 | 没有执行新算法构建、没有新 release |

用户说明 IMU 硬件存在已知问题，过去配置 `imu_rate=200` 时 VINS 效果可用，要求暂不处理。因此保留这个配置语义，在以后记录中同时给出配置值与真实频率，不修改设备输出、不重写时间戳或伪称 200 Hz 达标

## 2. 系统与运行条件

| 项目 | 实测 |
| --- | --- |
| 目标 | firefly@192.168.1.51 |
| 板型 | Firefly ROC-RK3588S-PC V12 MIPI(Linux) |
| 架构 | aarch64，8 核 |
| 系统 | Ubuntu 20.04.6 LTS，内核 5.10.160，glibc 2.31 |
| 内存/空间 | 约 31 GiB 内存；根分区约 193 GiB，空闲约 42 GiB，探索时使用约 79% |
| 网络 | eth0=192.168.1.51/24，未见默认路由，wlan0 DOWN |
| 已有 ROS/Python | /opt/ros/noetic；Python 3.8.10 |
| 已有工具 | gcc/g++、cmake、rsync/scp、systemd-run、lsusb/v4l2-ctl；PATH 未发现 perf |
| 权限 | firefly 属于 dialout/video 等组；sudo -n 可用 |
| USB | USB3 相机可普通用户访问；usbfs_memory_mb=1000 |
| 后台管理 | user manager 运行，Linger=no；不能据此直接承诺退出登录后 user service 存活 |
| 可采样资源 | thermal_zone 温度、CPU policy0/4/6 调频接口；当前 governor=interactive |

20.04/22.04 不改变“板端无需部署用户态依赖”的目标。它们只影响私有包的 ABI 兼容性验证；正式包不依赖现有 ROS、全局 SDK 或旧算法库。本轮不改系统版本、调频、时钟、USB 规则或系统服务

系统提供设备权限是基础镜像能力，用户态 env.sh 不能替代内核/BSP；当前节点可访问即可继续探索，后续独立验证新包的运行闭包

## 3. 工作区与可借鉴来源

| 位置 | 内容与用途 |
| --- | --- |
| ~/driver_ws/src/blackfly_driver_3.0 | 当前 FLIR 历史 C++ 驱动，可参考参数和 SDK 接口 |
| ~/driver_ws/src/gnw_500 | 本轮确认可收数的格纳威驱动，实际 UART=/dev/ttyS7 |
| ~/driver_ws/src/a100、g100_imu_publish | 另外的历史格纳威协议，不因文件存在就认为当前设备采用它 |
| ~/driver_ws/src/arena_camera、~/GigeCamera_ws | Lucid Arena 历史工作区，本轮实际相机不属于该型号 |
| ~/driver_ws/src/xsens_ros_mti_driver、mavros、imx296_mipi_driver | 其他设备历史内容，不纳入当前主线 |
| ~/3rdparty/spinnaker-3.1.0.79-arm64 | ARM64 SDK deb、头文件包及厂商配置脚本，可核验后作为来源 |
| /opt/spinnaker | 已安装 SDK、官方示例、文档和运行库；本轮用于探索 |
| ~/3rdparty/ArenaSDK_Linux_ARM64 | Arena 0.1.49，包括头文件、GenICam、示例和运行库 |
| ~/ros_project/vins_fusion | 历史 VINS 工程，config/flir_gnw 有现场配置候选 |
| ~/drpl_catkin_ws/src/EPLF-VINS | 其他算法，不并入新 VINS 主链 |
| ~/sh_files/p600 | 历史启动/录包脚本，说明过去组合的是 GNW500 + Blackfly multi + VINS |

`.bashrc` 自动加载系统 ROS 和 drpl_catkin_ws，所以正式远程任务必须显式初始化包内环境，不能照搬交互 shell 环境。历史脚本采用多个后台 roslaunch、sleep 和绝对路径，只作流程线索，后续统一任务管理不复制这套组合

本轮未在板端迁移源码、部署新平台、删除旧工作区或安装依赖。主机 `third_party/` 已建立可见入口，具体采用的源代码和 SDK 后续再按版本锁补齐；板端只应留运行数据和部署/探索文件，不作为新的 Git 开发仓库

## 4. 实际相机

USB 枚举为 `1e10:4000 Point Grey Research, Inc.`，SDK 读到：

| 字段 | 实际值 |
| --- | --- |
| 厂商/型号 | FLIR Blackfly S BFS-U3-31S4M-BD |
| 序列号 | 25162247 |
| 接口 | USB3Vision，SuperSpeed |
| SDK | Spinnaker 3.1.0.79 |
| 设备访问 | OpenReadWrite，普通 firefly 用户 |
| 当前输出尺寸 | 1024×768 |
| 传感器尺寸节点 | Sensor Width=2064，Sensor Height=1544 |

厂商 Enumeration 退出 0，未检测到 GigE 相机；Acquisition 退出 0，保存 10 张 1024×768 单通道 JPEG，全部能读取且有非零灰度变化。样本亮度存在变化，本轮不据此判断曝光/光照质量，也没有建立 20 Hz、长期稳定或硬触发证据

JPEG 仅为厂商探索示例输出，未来正式原始采集不能用这些有损图像代替 sensor_msgs/Image；原始像素、原始/设备时间信息应按配置保留，下游再进行明确的灰度转换、裁剪或缩放

Lucid SDK 的存在说明以前用过相关设备，不等于当前接的是 Lucid。厂商资料也区分 Arena GigE 与 Spinnaker USB3 接入，本轮以实际 SDK 枚举为准。[Arena SDK](https://thinklucid.com/arena-software-development-kit/)、[Spinnaker ARM 说明](https://www.teledynevisionsolutions.com/support/support-center/application-note/iis/using-spinnaker-on-arm-and-embedded-systems/)

## 5. 格纳威 IMU

串口节点为 `/dev/ttyS7`，root:dialout、0660，firefly 可访问；未发现当前使用的 ttyUSB/ttyACM 设备。原终端状态为 9600/canonical，不能用这个状态下的采样判断设备没有正确数据

探针只收不发，临时设为 115200/raw，退出恢复原设置。五秒中找到约 500 个帧头，其中 499 个完整 54 字节帧校验通过、没有候选校验失败；边界不完整帧不算丢包。加速度模长均值约 9.8223，与静态重力数量级一致

随后在独立 loopback ROS master 下直接运行现有 gnw_500 二进制，配置 port=/dev/ttyS7、baudrate=115200、imu_rate=200，观察话题 `/vins_intake/imu` 八秒：

| 指标 | 结果 |
| --- | --- |
| 观察条数 | 785 |
| 主机到达频率 / Header 频率 | 100.0008 / 99.9987 Hz |
| 有限数值条数 | 785/785 |
| Header 非递增 / 观察到的序号缺口 | 0 / 0 |
| 最大到达间隔 | 约 11.56 ms |
| 加速度模长均值 | 约 9.8220 |
| IMU/master 退出 | 均为 0，未升级到 TERM/KILL |

源代码将陀螺仪 deg/s 换成 rad/s，加速度直接发布，Header 使用 ROS 收到/解析时刻。它不是设备硬件同步时间戳；当前算法核心并没有读取 `imu_rate` 的配置键，所以这里的 200 属于驱动配置，VINS 仍依赖实际消息时间积分

话题序号无缺口不能证明 UART 从未丢字节或所有样本都被 VINS 消费。精确设备型号、协议手册、设备内部时钟与触发连线尚待确认，不因目录叫 gnw_500 就断言已识别具体 SKU

## 6. 现场配置与已有数据

历史 `config/flir_gnw/our_config.yaml` 使用 `/gnw_imu/data`、`/usb_camera/gray/image_raw`、512×512、固定现场外参初值和在线外参/时间偏移估计，配套 `left.yaml` 是 pinhole 模型。现场有多份不同后缀备份，**未确认哪份属于当前相机/镜头/裁剪与安装**；不复制到默认 EuRoC 模板，也不宣称标定合格

板上已有 EuRoC `~/datasets/MH_05_difficult.bag`、TartanAir 及 Handheld1 等数据；主机保留 MH_01_easy 与真值。v0.1 先统一主机和板端使用 MH_01_easy 单目 IMU，不将不同数据集的结果混作基线

已有 `.bag.active`、旧录包及历史输出保持原样，本轮不做重索引/修复或重跑算法。真实硬件初始化、运动轨迹质量、同步与现场标定属于后续正式验证

## 7. 暂存问题，当前不修

- 历史 VINS 的动态依赖同时出现 OpenCV 4.2 与 4.4，不用它充当新包的干净基线；新构建自然要隔离，暂不修旧安装
- 相机历史 resize 节点包含写死 ROI 和 Bayer 转换；当前硬件为单色型号。需要集成时再按实际像素格式最小适配，不在本轮改动
- GNW 解析器有重叠 memcpy、缓冲边界/成功返回语义等疑点；这次短时收数成功不等于代码已完整审计。仅在妨碍接入或可靠性验收时再处理
- 板端驱动源码不是完整可追溯 Git 上游，部分许可字段含糊；集成前记录来源/哈希并确认可使用范围。本轮只回收探针与来源摘要，不将厂商 SDK/历史驱动源码直接上传
- user service 的断开存活条件尚未验证；新任务管理要实际验收，不能把 nohup 或 start_new_session 的使用当作断线测试

用户已要求暂不处理历史代码和 IMU 硬件问题，本节作为后续需要时的路标，不扩大本轮工作

## 8. 证据、失败与可复查方式

Git 中的小型证据位于 [evidence/intake/20261028](../evidence/intake/20261028/README.md)，完整日志、源码阅读记录和厂商示例图像归档在本机 `experiments/platform-intake/001/`，由 Git 忽略。`SHA256SUMS` 固定小型证据和探针，SDK/源码原件哈希在来源清单中

保留两次初始探针局限：首次 list_camera 在没有 master 时等待超时，不是相机失效；首次按原 9600 终端状态被动采样无匹配校验帧，不是 IMU 失效。随后使用无 ROS 依赖的厂商示例与正确 UART 设置验证成功，不改写初始记录

SDK 示例没有发固件更新或保存 UserSet 命令，只完成临时 Acquisition；ROS 探针使用独立 master，结束恢复 UART 配置并确认无自有残留。板端临时目录仍可追溯，主机已经回收所需文件；本轮未验证新工程 release、算法精度、断主机网线、长时采集或驱动故障恢复
