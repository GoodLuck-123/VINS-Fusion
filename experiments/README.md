# 运行结果与实采数据

## Quick Start

主机每次结果保存为 `experiments/<实验名>/<host|board>/<运行序号>/`，板端任务保存在 `~/vins-workspace/experiments/<实验名>/<运行序号>/`，其中包含实际配置、包身份、轨迹、摘要、日志及本次录制的原始数据；不会覆盖上一次同名任务

探索记录已归档到本机 `experiments/platform-intake/001/`，小型可追溯证据另在 evidence/intake/20261028。这里的探针图像和日志不代表新平台算法验收

运行中只轮询摘要；大文件和原文日志按配置回收、校验。输入数据归 data，构建归 build，最终包归 releases；生成结果不提交 Git

已验收的完整回放为 `euroc-final/host/002/` 和 `euroc-final/board/002/`。故障/取消任务独立保留，不混入成功统计，小型记录见 evidence/v0.1
