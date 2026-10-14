# Fast DDS 板端运行环境验收

fastrtps02 退出 0；主机从同一签名 ROS 索引下载四个 ARM 包，逐包 SHA256 核验通过，独立 addon 包含 50 个文件并在板端逐一校验。原 SDK/运行包不变，6991 个原运行文件再次校验通过

rmw_fastrtps_cpp 下独立 VINS 节点及组件订阅就绪，组件卸载成功，两进程均退出 0。实际 maps 显示 addon 的 rmw_fastrtps/Fast DDS 库和原运行包的 OpenCV 4.2；ldd 无缺库。版本 Fast DDS 2.6.12 / rmw_fastrtps 6.2.10，未修改 C++ 源码或标定

无 bag 输入，不计入完整 VIO。ROS InRelease 验签及 Packages SHA256 在锁生成时核对，签名 key 已归档于 cross_sdk_20261014；此处保留 InRelease 和包锁。失败 HTTPS 记录另存，不计入成功统计
