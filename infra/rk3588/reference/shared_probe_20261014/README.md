# RK3588 共享缓冲计算探针验收

主机阶段 shared-probe-build01 / shared-probe01，板端 memfd 和实际 /dev/dma_heap/system 均通过，各 1000 帧、逐像素验证 1000、失败 0、结束 outstanding 0；两个后端两路摘要一致，结束审计无旧作业活进程

编译源提交 3c74022，部署校验脚本提交 6ef3c7c；Release 保留 -UNDEBUG。重建执行 bash infra/rk3588/scripts/prepare_shared_probe.sh，再用 vins-remote 上传 ../.infra/rk3588/shared-probe-payload 并运行 infra/rk3588/scripts/shared_probe.sh，使用新的日志目录

灰度 mono8，32×16，源 stride 64、池 stride 32；四槽位、独立进程、慢消费者和跨帧 owner，源端复制 1000 次 / 512000 字节，等待/复用各 996 次。实际 DMA heap 节点权限 0660 root:video，沿用现有用户权限；不改 chmod，不回退到其他 heap

验证现有生产代码的 CPU DMA-BUF 缓存同步、归还和元数据/像素正确性，没有真实相机、外部 GPU/RGA fence 或端到端零拷贝验收，也不是完整 VIO。主机 UTC 为阶段时间依据，板端墙上时钟偏差保留
