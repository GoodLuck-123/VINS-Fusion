# v0.2 真实硬件与验收

## Quick Start

v0.2 已完成真实相机/IMU接入、用户运动 VINS、私有依赖修复及实采数据双端回放。使用流程见 [03 使用指南](03_USER_GUIDE.md)

```bash
cp project.example.yaml field.yaml
./vins -c field.yaml record    # 只采集原始数据
./vins -c field.yaml run       # 真实硬件 VINS＋录包＋摘要显示＋回收
```

默认保持 IMU→相机 Line0 硬触发、2×2 binning 和现场标定初值。修改 `inputs.camera.device` 可选择合并、裁剪、触发、曝光及必要的设备身份/软件帧率；模板已注释选项。改变图像几何须核对标定，不能把软件链验收当作标定精度验收

版本标记：`vins-platform-v0.2.0`；源码/依赖锁/验证脚本和小型证据纳入 Git，SDK、install、缓存及原始数据不上传 GitHub

## 1. 准确产物与数据

| 目标 | 当前 install |
| --- | --- |
| RK3588 | `releases/v0.2.0/rk3588/802ecb78f1287171/install/` |
| 主机 | `releases/v0.2.0/host/b1e716cee0a1289f/install/` |

同目录含 tar.gz、package.json、SHA256SUMS；`releases/board.json`、host.json 指向最新准确产物。已验收归档 SHA256 分别为板端 `68cae69d5a0ecdd9bccb0243a095c4270c91bb7eee60ec67c3930ef173b1ba24`、主机 `8bccfb46893d9a61fe27891aca531b80878426c7853e62b1ebb53303296e227a`，机器可读清单在 [packages.json](../evidence/hardware-v02/packages.json)

板端当前包为 `~/vins-workspace/releases/802ecb78f1287171/install`，current 已选定该包。主机直接激活其 releases 中的不可变 install，避免再次复制/解包；任务和结果仍在独立工作区。空间整理仅删除已替代中间构建、开发候选包及已提取且可重下的 deb 缓存，v0.1 最终包和失败原始数据保留

本次用户运动原始数据在主机 `experiments/field-motion-v02/board/001/raw/`，约1.27GB、三卷，含1209组原图/处理图/metadata、6245条IMU。板端同任务保留原件；回传文件逐一 SHA256 核对。双端离线结果为 `experiments/field-motion-replay-v02/board/001/` 和 `host/002/`

## 2. 默认链路与相机选项

设备为 FLIR Blackfly S BFS-U3-31S4M-BD、序列号25162247，Spinnaker3.1.0.79 ARM64；GNW串口 `/dev/ttyS7`、115200。用户确认安装未变、历史内参正对应2×2合并，并完成本轮运动配合

旧 `p600/imu_mavros_cam.sh` 实际启动 spinnaker_multi：合并后的1024×768 Mono8在 x=256、y=128中心裁出512×512。新适配器保留该几何关系，去掉灰度相机上的 Bayer 转换；独立核对一帧处理图与原图ROI像素完全一致，见 [image-geometry.json](../evidence/hardware-v02/motion-001/image-geometry.json)

任务先建立录包订阅，清空启动前串口旧缓冲并获得 IMU，再接受相机图像。IMU硬件触发器独立于串口读取；程序不向其发送改频或触发配置。标称200参数保留，实际约100Hz，不重采样或伪造200Hz

| 实际选项测试 | 结果 |
| --- | --- |
| 默认2×2＋硬触发 | 图像约20Hz、IMU约100Hz；正常提前stop、原始数据按需补收通过 |
| 2×2＋软件触发＋手动8000μs曝光 | 86组三路帧，约20Hz，配对与退出通过 |
| 2×2＋自由运行＋自动曝光上限20000μs | 88组，约20Hz，配对与退出通过 |
| 1×1＋软件触发＋中心裁剪 | 9组，约2Hz；仅完成收数/配对验证，未达到请求的20Hz，不作为默认生产配置 |
| 恢复默认硬触发与2×2 | 87组，约20Hz，已恢复现场模式 |

非默认1×1的吞吐限制需后续专项定位；未用降速掩盖或将其称作20Hz通过。默认生产配置及现场标定仍以2×2为准。其余 SDK 策略固定为Mono8、增益0、Gamma关闭、黑电平0、decimation1、零硬件offset；启动记录保留生效几何和触发参数

原始记录是相机输出的合并后采样区域，不是传感器所有物理像素；处理图单独录包。相机metadata保留设备帧号、设备纳秒与接收纳秒；GNW保留原始串口块，包尾SUM16不是设备时钟。ROS Header为接收/解析时间；物理硬触发已确认，时钟映射和标定精度未独立验收

## 3. VINS与回放验收

| 验证 | 初始化 | 轨迹条数 | 图像末帧差 | 播放/排空秒 | 子进程累计CPU秒 |
| --- | --- | --- | --- | --- | --- |
| 用户真实运动 | 1次 | 257 | 0.050 | 采集约60秒 | 原始state保留 |
| 正式包板端回放 | 1次 | 257 | 0.050 | 65.57 / 5.13 | 148.32 |
| 正式包主机回放 | 1次 | 251 | 0.050 | 64.46 / 5.07 | 28.76 |

各轮进程均退出0；正式包的双端回放没有强制清理。RSS/PSS为直接受管进程的采样峰值，详见各state.json，不等于整个进程树内存；无DDR/功耗或真值精度结论。未直接埋点证明内部队列为空，也未以本轮实验宣称实时性或跨架构轨迹严格相同

首次用户运动时发现SDK日志后端落到全局前缀，该轮是“真实运动/VINS功能证据”，不能单独证明私有环境。修复后用正式包完成真实静态收数、全部SDK实际maps核验，再重放同一段运动数据。按用户要求不再重复运动；最终版未重新开展一次新的现场运动或精度标定

源码对比确认：本版未改v0.1的VINS求解器、camera_models、观察器和核心依赖版本，原生−6线程生命周期修复继续保留。实采无真值，本轮证明采集、运行、回收和双端重放闭环，用户已目视确认位姿正常；不据此声称绝对精度合格

## 4. 修复与失败保留

- 静态001：只缺最后处理图。自有信号标记避免 roscpp 在一组帧尚未发完时关闭传输；原始失败bag、日志和小型证据保留
- 软件触发001：仍缺最后帧，定位到 Publisher 析构早于作用域外刷新。将停止采集/刷新移入其存活区间后重测通过，未延长重试或放宽配对验收
- 首次SDK隔离失败：GenApi通过dlopen加载日志后端，单查DT_NEEDED会漏库。补齐厂商辅助.so及GenTL，最终实际maps只允许包内库和OS glibc/loader；[最终maps](../evidence/hardware-v02/runtime-maps-private.json) 无非预期全局库
- 主机回放001：沙箱禁止本地ROS端口，EPERM；不修改算法，改用已授权本机环境后host/002通过

每个修复单独提交，先保留失败再串行重测。冻结的46个历史分支/tag未移动；最终检查在 [final-audit.json](../evidence/hardware-v02/final-audit.json)

## 5. 复现脚本与SDK来源

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
# 板端需空闲：下面脚本会短时切换SDK选项，结束恢复默认硬触发
.venv/bin/python tests/hardware_acceptance.py
# 使用上文已保存的三卷运动数据，不要求再次移动设备
.venv/bin/python tests/replay_hardware.py board
.venv/bin/python tests/replay_hardware.py host
.venv/bin/python tests/final_v02_audit.py
```

21项配置/评估单元检查通过；GNW协议对所有分包位置、噪声、校验错误恢复和连续帧进行ASan/UBSan检查通过，测试源为 tests/cpp/gnw_protocol_test.cpp。当前沙箱不支持LeakSanitizer，单独关闭泄漏检测，未关闭地址/未定义行为检查

`./vins build/run/record` 优先复用 cache/archives 的三个锁定SDK归档；缺失时用配置中的SSH身份从已知板上原始归档目录只读回收，逐一核对SHA256。只用dpkg-deb -x提取，不运行安装脚本，不从已安装/opt/spinnaker抽库

新板没有原归档时，从 [FLIR官方SDK页面](https://www.teledynevisionsolutions.com/products/spinnaker-sdk/) 获得同版本ARM64的 libspinnaker、libspinnaker-dev、libgentl 三个3.1.0.79 deb，放入 cache/archives 后重试。版本、精确文件名、SHA256及本次种子路径在 buildkit/spinnaker.lock.json，提取到可见的 third_party/spinnaker

GNW旧源码许可字段含糊，旧相机驱动也有固定ROI/Bayer疑点；本版仅保留来源哈希/协议事实并编写最小适配器，不复制来源不明代码或厂商头文件进Git。系统内核、glibc/loader、设备节点/权限及SSH、rsync等基础工具是镜像兼容条件，当前板子无需另装ROS、Python包或SDK
