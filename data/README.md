# 实验输入

## Quick Start

将输入 bag 与真值放在这里，或在复制后的项目配置中指定其他路径。v0.2 模板默认真实硬件，dataset 字段在 sensor 模式不使用；回放时填写单个 .bag 或包含分卷的目录。实采数据可直接引用 experiments 内 raw 目录，无需再复制

原主机已有数据位于 `/home/eric/projects/data/euroc/`，可先在用户配置中引用，不必重复搬运大包。原件不移动、不改写

输入不与构建产物混放；每次运行输出及新录制的原始数据归 experiments，最终运行包归 releases。本目录数据 Git 忽略
