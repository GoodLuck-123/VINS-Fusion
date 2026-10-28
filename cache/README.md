# 可再生下载与工具环境

## Quick Start

run/build 自动按锁准备本目录，无需手动搭 ROS。首次主机需联网且具备足够空间；板端无需联网

## 用途

archives 为校验后的归档，toolchain 为 ARM64 交叉工具链，sysroot 为锁定目标环境，host-env 为隔离原生 ROS 构建环境，tools 为固定版本工具，uv 与 mamba 为各自缓存

此处不是上板产物；不要复制某个零散环境替代 releases 中的完整 install。源码在 third_party，实际构建在 build，最终包在 releases。锁保存在 Git 中，下载和环境不入 Git
