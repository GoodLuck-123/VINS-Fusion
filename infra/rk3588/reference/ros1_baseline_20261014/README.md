# RK3588 ROS 1 一轮完整双目参照

实际仅回放一次，运行包/bag 哈希和 bag 左右图各 3682、IMU 36820 通过；1831 姿态、1819 匹配、末帧覆盖，一次初始化、无重置/配对丢帧。输入计数仅为 bag records，没有新增原节点实收计数；源端资源未采，VINS 全线程 CPU/RSS/PSS 单列

rosbag/ROS master 退出 0，原 VINS 清理 abort −6 如实保留，不叫正常退出。外层 ros1-baseline01 失败是回收后的主机评估不支持 --label，事件/错误日志保留；修正后 ros1-evaluation01 只对既有轨迹评估，未重跑或重新上传。主机同一 uv.lock/evo/SE(3) 无尺度校正/0.01 秒匹配，结束审计无旧作业活进程

运行包旧 metadata source_commit 实为 annotated tag 对象 329339700de632ce65c928d3dd229f1befa95a19，剥离至主机构建提交 30790b0。summary.json 明确两种对象，冻结运行包/原 metadata 不改；未来打包脚本已使用 ^{commit}。原 VINS/core/config 与 master 8c7c8d2 相同，ARM Focal/GCC9/传递依赖差异不只归因 ROS 版本

日志/CSV/TUM/telemetry gzip 保存，原文件 SHA256 在 summary.json，归档 SHA256SUMS 独立校验。板端墙上时钟未同步，按主机阶段 UTC 与单调计时；排空成功不是实时性通过，DDR/功耗不可用
