# 软件触发退出测试：失败保留

85 原图/metadata、84 处理图，仅末帧84缺失。NoSigintHandler 已避免 ROS 提前 shutdown，但相机 Publisher 在 try 作用域结束时会先于作用域外的刷新等待被析构，仍可能丢弃最后排队消息

将 EndAcquisition 与刷新等待移入 Publisher 存活的作用域，再 DeInit/ROS shutdown；不叠加更长等待或放宽三路数量与时间配对检查。GNW 的刷新本就在 Publisher 存活区间内，不做同类额外修改

完整失败 bag 保留在板端 experiments/field-software-v02/001/raw；主机保存状态、日志和清单，raw_data=on_request 尚未下载原 bag
