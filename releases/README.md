# 最终运行包

## Quick Start

执行 `./vins deploy` 自动构建或复用 ARM64 包，显示传输进度并在板端验包；正常实验直接 `./vins run` 即可

## 目录

`board.json` / `host.json` 记录最新产物准确路径。最终文件位于 `v0.1.0/rk3588/<包指纹>/` 或 `v0.1.0/host/<包指纹>/`，包含完整 install/、tar.gz、package.json 和 SHA256SUMS

部署整个 install，不单独取 bin。手动运行前 `source /实际路径/install/env.sh`，板端无需安装 ROS/Python 包。硬件/ABI 兼容边界及完整流程见 docs/03_USER_GUIDE.md

目录名中的指纹用于版本追溯，日常不需要手动输入；CLI 统一管理板端 current 和不可变包目录。产物不纳入 Git
