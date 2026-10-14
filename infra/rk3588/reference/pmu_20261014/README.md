# RK3588 完整 PMU 对照

两轮双目 standalone copy/share 各一次，完整输入/末帧、一次初始化、无重置/配对丢帧、1831 个姿态/1819 匹配、正常退出及主机评估通过，结束审计无旧任务活进程。四类用户态 CPU 事件均可读、无错误、time_running=time_enabled，不做复用缩放

计数范围为继承到原生节点全部后续线程，包含 exec/启动/清理与短 Python gate；资源 CPU/RSS/PSS 是 VINS 订阅就绪至排空，不包含源端。CPU/cache 诊断不替代 DDR 带宽或功耗，板端权限仍为原值 2

大日志和 TUM 导出 gzip 保存，summary.json 保留原文件 SHA256，原文件在工作区。算法/标定、运行包及输入保持不变；一次观察不作为确定提速结论，排空含稳定等待，不等于逐帧实时性
