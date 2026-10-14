# ARM 固定版本视觉库验收

主机交叉编译、板端运行及动态库闭包验证通过；探针源码和重建脚本位于 infra/rk3588/probes/legacy/ 与 scripts/，全阶段日志在 ../results/rk3588/legacy05/，板端原日志在 legacy-smoke01/

Ceres 启用宏集合与原生桌面一致，两个实际稀疏后端均求解 x=10。带 padding 灰度输入的 GFTT/LK 和只读输入检查通过，不代表 VINS 或完整共享协议已验收

更正：旧冻结 legacy03_failure/README.md 关于原生 SuiteSparse 版本不同的说法未核实且不正确；现在头文件复核确认原生/ARM 均 5.10.1，CXSparse 均 3.2.0。保留原归档和哈希，用本说明更正。实际传递依赖差异为原生 glog 0.6.0/ARM 0.4.0，原生 OpenBLAS 0.3.34/ARM Netlib 3.10.0，不能宣称全部依赖完全相同
