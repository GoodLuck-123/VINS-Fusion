# ROS 1 依赖下载验收

ros1-fetch01 退出 0，四个源码和 36 个工具链 + 807 个 SDK 包按锁下载并核验 SHA256，随后 --offline 重验全部缓存、完成标记与转换成功。GCC 9.4 在主机实际运行，原 Carotene 参数空翻译单元编译通过；目标视觉库/节点与板端 ABI 尚待验收

下载内容均 Git 忽略，普通 clone 只取锁与 .gitkeep，一条 fetch.py 补齐。原 ROS 2 SDK/源码/运行包不动，ROS 1 工作区来自 master 最新 8c7c8d2，独立 Focal/Noetic ABI 前缀。控制台 gzip 保存，validation.json 记录原 SHA256；包锁和签名元数据见前一阶段归档
