# 固定实验目录与具名任务验收

## Quick Start

普通使用见 docs/11_RK3588_USER_GUIDE.md 和 docs/12_VINS_REMOTE.md。主机重新验证时使用新的输出目录和未用任务名：

```bash
python3 infra/remote/probes/workspace_check.py --tool ../.infra/bin/vins-remote \
  --output ../results/new-workspace-check --name workspace-check02
```

探针只对空闲板端做无数据检查，不重放 VIO；沿用既有已验收 v0.1 包和 EuRoC 数据，路径从工具配置派生，稳定 bag 链接不覆盖其他文件。测试前确认板端未运行 ROS/VINS，任务完成后保存日志

## 结论与范围

14 项原生集成、7 项发布脚本测试通过。真实板端已安装工具和可分发工具箱均验证默认上传/环境目录、双向 SHA256、具名任务、拒绝覆盖与重复回收，包内 4217 文件校验及订阅就绪通过；原 VINS 停止 −6 单列，roscore 0。没有新 VIO 输入或性能统计

board_final.json 记录最后无残留进程、安装入口不变和测试上传文件清理；两次具名检查任务保留于 runs/，完整主机日志位置见 summary.json。旧 v2 工具箱、v0.1 包、已有冻结证据和 core/config 均核对未改。此次只提交生产分支，不打新 tag

installed/portable 前缀区分实际入口，两者文件不混入算法统计；host_build_metadata.json 用原提交与逐文件 SHA256 标记本次修改源码，最终提交见 Git 历史
