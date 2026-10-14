# Ceres 1.14.0 / 解包 ARM SDK 配置失败

OpenCV 4.2.0 已构建安装，Ceres 配置失败，未生成 Ceres；缺少 BLAS/LAPACK alternatives 链接，且旧 FindTBB 要求已移除的 tbb_stddef.h

改为查找 SDK 内实际 blas/lapack 子目录，明确保留 SuiteSparse/LAPACK；readelf 确认此 SDK 的 libspqr.so 不依赖 TBB，因此关闭可选 TBB 探测，不切换求解器线程模型。独立新目录配置已找到 SuiteSparse 5.10.1、LAPACK 和 BLAS，未修改下载源码或板端系统

旧原生 SuiteSparse 为其他版本，ARM 使用 Ubuntu SDK 包；OpenCV/Ceres/Eigen 版本保持原样，完整板端精度仍需实验验收
