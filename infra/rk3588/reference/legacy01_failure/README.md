# ARM 视觉库首次配置失败

主机 fresh shell 没有 Ninja，首次 Eigen 配置前退出 1，未生成视觉库。改用已有 GNU Make，在新的 build-legacy 目录重建；原构建目录和日志保留，不改依赖版本或算法
