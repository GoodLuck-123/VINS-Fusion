# 新平台 v0.1 验收

## Quick Start

用户流程见 [03 使用指南](03_USER_GUIDE.md)。当前为候选验收记录，尚未打版本 tag；真实相机/IMU 属于 v0.2，本记录中的算法验证使用 EuRoC MH_01_easy 单目＋IMU

```bash
.venv/bin/python -m unittest discover -s tests -v
./vins run --host
./vins run
./vins status
```

完整运行产物在 experiments，小型摘要与校验值纳入 evidence/v0.1。历史 intake 证据不改写；失败试验保留，与成功统计分开

## 1. 算法与退出修复

VINS 基线为原生 `be55a937a57436548ddfb1bd324bc1e9a9e828e0`。仅改 rosNodeTest 和 Estimator 的线程收尾：循环观察 ROS 停止状态，等待 IMU 时可退出，join 图像同步线程，后端只 join 已启动线程。原生局部 std::thread 在 main 返回时仍可 join，析构调用 terminate 并触发 SIGABRT，Popen 中表现为 −6；本版保留真实退出码，不吞掉失败

对照节点及 backend 从原生提交重建，复用相同目标的 OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、cv_bridge、相机模型和私有 ROS 依赖。参考构建/打包/回放脚本在 buildkit/reference.py 和 tests/reference_*.py，仅用于开发验收，不作为用户入口

| 目标／版本 | 完整位姿 | ATE RMSE m | 相邻位姿 RPE RMSE m | VINS 退出 |
| --- | ---: | ---: | ---: | ---: |
| RK3588 原生参照 | 1831 | 0.161051 | 0.003019 | −6 |
| RK3588 最小修复 | 1831 | 0.160411 | 0.003023 | 0 |
| 主机最小修复 | 1831 | 0.185564 | 0.002938 | 0 |
| 主机原生参照 | 1831 | 0.185564 | 0.002938 | −6 |

同一目标串行回放，rate=1、同一配置；每次结果有独立任务身份。单次对照不证明性能收益或统计等价，不要求不同架构轨迹字节相同。原生参照虽产生完整轨迹，任务仍按收尾失败处理

评估使用 IMU/body 真值，最近未使用时间戳关联 ≤10 ms，SE(3) 刚性对齐、尺度固定 1；RPE 为相邻已匹配位姿间相对平移误差，不与不同间隔/不同关联规则的 RPE 混比。评价实现用已知旋转平移和尺度错误的数值测试核对

## 2. 必须完成的验收项

| 项目 | 状态／证据 |
| --- | --- |
| 配置与评估数值检查 | 12 项通过，包含单位、NaN、变换矩阵、重复键、刚性对齐及不隐藏尺度误差 |
| host/ARM64 构建 | 两目标完成，只构建开环 camera_models/vins_node/observer |
| 主机完整播包 | 已通过，位姿 1831、初始化 1 次、所有进程退出 0 |
| RK3588 完整播包 | 已通过，位姿 1831、初始化 1 次、所有进程退出 0 |
| 交互终端 | 已验证 projects/vins、私有 Python 与当前任务 master |
| 实际私有库加载 | 主机进程映射通过；板端待最终包验证 |
| 异常退出、超时、重复启动、正常停止 | 待验证 |
| 无输入／等待 IMU 的正常退出 | 待验证 |
| 损坏包、安装路径迁移 | 待验证 |
| 监控开销 | 待固定区间开关对照 |
| 最终候选包回放、断开查看后接续与回传 | 待验证 |

成功标准为轨迹有限、严格时间递增、覆盖最后图像时刻、全部自有进程正常退出及回传清单匹配。内部队列长度没有埋点，queue_empty_verified=false；回放和后续收尾时间分别记录，不据此声称实时通过

## 3. 已遇到并保留的失败

- 最初包内 Python 模块/工具重定位不全：构建日志在 build/package-*.log，后续通过真实 ROS 启动继续核验
- 板端 euroc-mono/001：用整个 bag 结束时间判断输入末帧，未考虑其他话题更晚结束；修正为所选输入话题自己的索引，无需改算法
- 主机空间不足：安全检查拒绝解包。只清理本轮重复开发产物和可再生下载缓存，记录在 build/pruned-development-artifacts，不降低 4 GiB 保留值
- 主机 euroc-mono/001：缺少 catkin 前缀标记，rosout 查找失败；补齐标记与必要可执行文件检查
- 主机 euroc-mono/002：rosbag 动态插件不在 ELF DT_NEEDED 闭包中，读取 bag 失败；显式打包 pluginlib 声明的库，FATAL 作为失败信号，避免退出 0 但无数据时长等收尾
- 旧候选发布 completed 早于日志归档和 files.json，首次 pull 遇到清单尚未出现；改为归档和清单完成后再发布最终状态，旧任务直接补收，不重跑算法

- 短回放发现本 bag 的 chunk 起点为 1403636579.8092628，连接索引最早记录为 1403636578.946206。Python bag.get_start_time 使用 chunk，而 rosbag::View 播放器使用全连接索引；统一到索引起点计算 start/duration 和目标末帧，未改数据或放宽阈值。实现依据为 [ROS 官方播放器源码](https://github.com/ros/ros_comm/blob/noetic-devel/tools/rosbag/src/player.cpp)，并用 15/30 秒实际回放回归
