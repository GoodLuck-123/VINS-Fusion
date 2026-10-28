# 中间和历史构建

## Quick Start

一般用户直接 `./vins run`。只构建用 `./vins build --target host` 或 `--target board`，详细日志为 host-build.log / board-build.log

## 用途

`<目标>/<源码与依赖指纹>/` 存 CMake 中间产物、隔离前缀和构建记录，`<目标>/current.json` 标识可复用构建。host/workspace 是主机任务的隔离运行区；host 直接激活 releases 中已校验的不可变包，不再重复复制与解包，任务目录仍独立

最终可部署包在 releases，不从此处挑选零散二进制。构建指纹变化不覆盖旧产物；空间不足时可在停止构建后清理已替代构建，保留验收证据和正在使用的包
