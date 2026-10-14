# 共享库消费端链接失败

legacy04 的库构建退出 0，但尚未接受为里程碑。消费探针链接失败：间接 BLAS/LAPACK 缺少 rpath-link，OpenCV calib3d 存在未定义 __frexp

SDK 的 usr/lib/aarch64-linux-gnu/libm.so 原为绝对链接，在 x86 主机无法解析；链接器退回静态 libm.a。统一解包脚本将目标 SDK 的绝对链接改为 sysroot 内相对链接，保存 36 项转换记录，原 832 个包锁和压缩包 SHA256 不变。工具链补齐目标间接库查找目录，完整重建库，避免复用包含错误静态数学库的产物

consumer_link_recheck.log 是调整 sysroot 链接后、重建视觉库前再次检查旧库时的实际输出，不冒充首次探针完整 stderr。原始构建事件与控制台保留，旧库前缀及构建目录也保留，不计入成功统计
