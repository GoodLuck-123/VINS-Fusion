# ROS 1 线程退出修复验收

## Quick Start

普通使用见 docs/13_BOARD_CLI.md，主机交叉构建与成对交付见 docs/08_RK3588_WORKFLOW.md 第 5 节。用户命令仍是 check/run，默认 install 选择 v0.2.1；v0.2 tag/包保持冻结，补丁只按 commit 追溯

## 修复与验证

fb4ad05 只在两个 C++ 文件修改停止与 join：同步线程在 ROS 停止时结束，main join；后端主循环及等待 IMU 响应停止，析构只 join 可 join 的线程。未改图像配对、队列、特征/求解、参数或标定。新构建在独立 ros1-shutdown-ws，旧 70 个 ELF 和两版冻结压缩包哈希未变

真实 RK3588 无输入、单线程、等待 IMU 三场景均 VINS/master 退出 0；等待 IMU 的测试先确认真实执行了 wait for imu，再停止。首次只换入口而加载旧后端库导致超时的证据保留，后续成对更新 vins_node/libvins_lib.so 后通过；没有追加 C++ 绕过修补

同一 run、数据与配置串行运行旧版/修复版，两轮各一次；各自 1831 姿态、1819 真值匹配、一次初始化、无重置/配对丢帧、末帧一致。旧版退出 playback=0/vins=-6/roscore=0；修复版全部 0。ATE/RPE 与预设 5%+1mm/5%+10um 容差见 accepted-runtime.json；这是功能/精度回归，不宣称性能改善或统计等价

资源对各进程分别采样，最后 CPU 样本是全线程累计 CPU 的下界，RSS/PSS 是采样峰值，回放和收尾时间分别记录；不把峰值相加，DDR/功耗不可用。原始进程采样 gzip、轨迹、日志及评估均附 SHA256，可回查完整日志

打包器只替换经构建/板端哈希一致且依赖列表不变的节点/后端库，保存新源码提交和基包来源；错误哈希组合已实测被拒绝。正式包验收停止必须为 0，另测取消/超时/启动失败，并在恢复故障注入后再核全量文件

发布前文档复核修正一处 cd 示例遗漏补丁号：首份内部验收包完整保留为 package-doc-draft，板端移到 validation/v021-doc-draft；未改写已发布包/tag。最终包与草包差异仅文档、来源链接和清单/打包提交，所有程序/库相同，见 package-doc-diff.json；最终 accept02 重新验收并选择默认 install
