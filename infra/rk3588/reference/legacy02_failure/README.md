# GCC 11 / OpenCV 4.2.0 Carotene 参数兼容失败

Eigen 安装完成，OpenCV 配置完成，Carotene 编译因 GCC 11 不接受旧参数 ipcp-unit-growth 而退出 2，未安装 OpenCV/Ceres

GCC 将该参数改名为 ipa-cp-unit-growth，官方记录：https://gcc.gnu.org/legacy-ml/gcc-patches/2020-01/msg00425.html

仅改参数名称，数值 100000、其他 inline 参数和 ARM 默认 Carotene 保持原样。补丁纳入 infra/rk3588/patches/，构建脚本复制锁定源码到独立目录再应用补丁，不修改下载目录或旧失败构建；此阶段不计入成功统计
