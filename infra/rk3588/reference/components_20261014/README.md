# RK3588 组件与 owner 对照

五轮新增配置各一次，双目 standalone/copy 复用已验收基线，不重复回放。所有输入/末帧、一次初始化、无重置/配对丢帧、1831 个姿态/1819 个匹配、退出均通过；自动主机 uv.lock/evo 评估完成，结束审计无旧任务活进程

share 灰度入口零物化；composed 前六条样本源端和消费端 message/pixels 相同，copy 的 Mat 独立、share 的 Mat 借用原像素。此证据不覆盖真实相机、DMA heap 或端到端零拷贝

三组 copy/share 的单轮 CPU 差异均不足 0.5%，不同配置轨迹有小幅差异，不沿用桌面字节一致结论、不宣称确定提速。CPU 范围 standalone 只含 VINS，composed 包含 VINS+播放器+容器，详见 summary.json。排空含稳定采样等待，不等于逐帧实时性

大日志用 gzip 保存，summary.json 同时保存解压前 SHA256；完整原日志保留在 ../results/rk3588/board-components01/trial/board。SDK/运行包/数据不变，无算法或标定改动
