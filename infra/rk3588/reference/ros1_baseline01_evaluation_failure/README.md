# ROS 1 已完成回放后的主机评估失败

ros1-baseline01 板端工作退出 0，bag/运行包哈希、bag 计数、一轮完整回放、1831 姿态/末帧及日志回收均完成。ROS master/rosbag 退出 0，原 VINS 清理 abort −6 如实记录

外层阶段失败是主机评估器不支持 --label，而调用入口误沿用 ROS 2 参数。只移除不支持参数，并以 --evaluate-only 对已回收数据恢复评估，不重新上传/回放，不覆盖原失败事件或日志，也不把该失败标为整个阶段成功

另将未来打包来源解析改为 ^{commit}，已有冻结 build_source.json 的 source_commit 实为 annotated tag 对象 329339700de632ce65c928d3dd229f1befa95a19，可剥离至构建提交 30790b0；已有包/哈希保持原样，在验收报告中记录此对应关系
