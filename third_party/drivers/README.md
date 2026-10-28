# 现场设备适配

本目录是本工程编写的最小 ROS 适配器，与主工程按 GPLv3 分发；不是旧工作区源码的复制。Spinnaker 厂商文件单独下载、私有提取到 `third_party/spinnaker`，不纳入 Git

GNW-500 协议由板上现有源码及实际 54 字节帧核对，来源哈希见 `evidence/intake/20261028/source-sha256.txt`。只采用已验证的线格式、SUM16、加速度 m/s² 与角速度 deg/s→rad/s；不采信未核验的 RPY 约定。包尾校验和不是设备时间戳

相机保留 2×2 合并后的完整 Mono8 图像，VINS 输入采用明确的中心裁剪。ROS Header 为主机接收时间；独立 metadata 保留设备帧号、设备纳秒及接收纳秒，不能据此宣称硬件同步。GNW 原始串口块同样留存，bag 记录时间为接收侧时间
