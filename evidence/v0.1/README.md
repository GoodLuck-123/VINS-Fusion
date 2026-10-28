# v0.1 验收证据

## Quick Start

用户操作见 docs/03_USER_GUIDE.md；完整解释见 docs/04_VALIDATION.md。这里保存经过核验的小型记录；大轨迹和压缩日志保存在 experiments，不纳入 Git

| 验证 | ATE RMSE m | RPE RMSE m | VINS 退出 | 回放 s | 收尾 s | 子进程 CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reference-host | 0.185564 | 0.002938 | -6 | 185.782 | 5.063 | 113.766 |
| patched-host | 0.185564 | 0.002938 | 0 | 185.617 | 5.083 | 113.362 |
| reference-board | 0.161051 | 0.003019 | -6 | 186.823 | 5.114 | 542.572 |
| patched-board | 0.160411 | 0.003023 | 0 | 186.960 | 5.160 | 582.894 |
| release-host | 0.185564 | 0.002938 | 0 | 185.774 | 5.090 | 117.477 |
| release-board | 0.160457 | 0.003029 | 0 | 186.844 | 5.212 | 540.876 |

## 文件说明

acceptance.json 关联精确包、归档 SHA256、构建/实现提交和任务；每个任务子目录有原始状态、评估协议、传输证明与实际参数。runtime-maps 证明私有库实际加载路径；lifecycle/shutdown/observer-inputs/package-checks/board-recovery 记录对应故障与迁移验证

monitor-overhead 是同区间 30 秒的一次串行开关对照，只关闭话题观察器；任务监督和资源采样仍开启。CPU 总量是全部已等待子进程线程累计秒，per-process CPU 为采样下界，RSS/PSS 为观察峰值。未测整套监控（含主机 SSH 客户端）的全部成本，不将单次差异解释为性能收益

未直接观测 VINS 内部处理队列；末帧覆盖与文件稳定不声明实时性。硬件采集、标定与同步质量留待 v0.2/v0.3，当前没有实际相机/IMU 算法通过的结论
