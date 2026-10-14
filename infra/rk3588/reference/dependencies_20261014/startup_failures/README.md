# 构建验证中的启动失败

首次直接链接选择了工具链的 cross libc 脚本，其绝对路径不适用于 ARM sysroot；修正目标库查找顺序后链接通过

随后两次验证命令未在 CMake 构建阶段保留编译器 LD_LIBRARY_PATH，另一次从 zsh source 了 bash 环境文件；构建未产出 hello，缺失 payload 的板端运行均退出 1。原始远端日志保留，均不是 VIO 实验，也不计入成功统计

固定 cross_env.sh 并在同一 bash 中配置/构建后，cross-smoke05 正常退出 0
