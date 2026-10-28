# 2026-10-28 新平台起点与板端探索证据

## Quick Start

结论先读 [02 板端探索](../../../docs/02_BOARD_DISCOVERY.md)；原始小文件由本目录 SHA256SUMS 校验，完整本机归档在仓库内 `experiments/platform-intake/001/`

```bash
cd evidence/intake/20261028
sha256sum -c SHA256SUMS
```

| 文件 | 用途 |
| --- | --- |
| frozen-refs.json | 原有 5 个本地分支和 41 个 tag 的精确对象，含 annotated tag 的 peeled commit |
| removed-configs.json | 清理的旧场景/可视化/环境配置，原生恢复点及原 SHA256 |
| board-summary.json | 本轮实际设备、已做与未做事项，不代替原始探针结果 |
| source-sha256.txt | 板上可借鉴的 SDK deb、驱动源码和现场配置来源哈希 |
| board-sdk-probe.txt | 厂商枚举、10 张成像、退出状态及图像基本统计 |
| uart-probe.json | 115200/raw 下只收不发的五秒串口样本摘要 |
| imu-ros-probe.json | 既有 ROS 驱动的八秒话题观察、频率、数值和退出 |
| board-readonly-probe.txt | 首次无 master/错误终端状态下探针的局限，保留失败 |
| board-probe-cleanup.txt | 探针 master 清理、串口恢复和来源许可字段记录 |
| probes/ | 可重建的探索脚本，不是平台 CLI 或正式运行包 |

探索脚本依赖当前板上既有系统 ROS/SDK，仅作本轮复查；后续正式验收不能借此绕开新包依赖闭包。重复运行 ROS 探针需选择一个新的工作目录，脚本故意拒绝覆盖原报告
