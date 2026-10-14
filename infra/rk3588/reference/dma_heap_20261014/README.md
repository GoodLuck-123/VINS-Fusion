# RK3588 完整共享传输验收

每配置一次、串行回放，完整输入/末帧、一次初始化、无重置/配对丢帧、主机评估及退出通过；像素/时间戳摘要一致，所有共享槽位归还，结束审计无旧作业活进程

分别报告 VINS/源端全线程 CPU 与 RSS/PSS；源端仍复制像素到池，排空后成功不称为实时通过。单轮性能差异不当作稳定收益，DDR/功耗不可用

日志/CSV/TUM/telemetry 以 gzip 保存，summary.json 保留每个原文件 SHA256，SHA256SUMS 校验归档文件。主机事件 UTC 为时间依据，板端墙上时钟偏移保留；固定运行包、addon、bag、DDS 配置及完整方案见 drivers/plan.json 与 board/<trial>/run.json
