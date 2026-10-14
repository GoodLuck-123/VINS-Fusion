# ROS 1 板端依赖下载

更新日期：2026-10-14

本分支从 master 最新 8c7c8d2 建立，原生桌面 ROS 1 记录与历史 tag 保留；ROS 2 板端实现留在 codex/rk3588-ros2。普通 clone 只取得锁和空目录，不自动下载依赖

联网 Linux x86_64 主机在仓库根执行：

```bash
python3 infra/dependencies/fetch.py
```

需要系统 Python 3、curl、dpkg-deb，无需安装系统包。脚本核验 SHA256 后解包，下载/源码/工具链/sysroot 忽略；已有内容与锁不符时停止。--offline 只用缓存，--cache-from 可重复指定已校验缓存，--sources-only 只取通用源码

| 内容 | 固定版本 / 范围 | 目录 |
| --- | --- | --- |
| OpenCV / Ceres / Eigen | 4.2.0 / 1.14.0 / 3.3.9 | dependencies/sources/ 各自版本目录 |
| cv_bridge 源码 | 1.16.2 | dependencies/sources/cv_bridge_ros1/1.16.2 |
| 交叉工具链 | Focal GCC 9.4，36 个 amd64/all 包 | dependencies/toolchain/root |
| Noetic SDK | Focal/Noetic final，807 个 arm64/all 包 | dependencies/sysroots/ros1-noetic/root |

官方 Noetic 平台为 Focal / Python 3.8 / Boost 1.71，独立前缀保持这组 ABI；板端系统继续 Ubuntu 22.04。当前已完成索引验签、依赖锁、四个源码/843 个包下载及离线重验，编译及实际板端兼容性待验收，不能当作已运行 ROS 1。与 ROS 2 的编译器/传递依赖差异需单列，性能变化不能仅归因于 ROS 版本

[source lock](../dependencies/sources.lock.json) 与包锁 dependencies/locks/*.json 记录版本、架构、URL 和 SHA256。来自私有 APT 空状态的依赖解析，ROS snapshot 使用官方 Dockerfile 固定的独立公钥指纹；所有包 SHA256 取自已认证 Packages，而非 print-uris 的 MD5。签名索引、请求与解析证据见 [归档](../infra/rk3588/reference/ros1_sdk_discovery_20261014/)

解包后将绝对目标符号链接改为 sysroot 内相对链接；必要的 Noetic CMake libpython 导出加 CMAKE_SYSROOT，变化记入 sysroot 审计 JSON，原包哈希不变。不执行 postinst、不改主机或板端系统；交叉构建与运行包另验收，不能直接部署 SDK 自带 OpenCV/cv_bridge 代替固定源码重建

安装/构建、数据和完整日志仍在父工作区 .infra/、data/、results/，仓库根不建软链接。下载只在主机执行，不在离线板端执行此脚本，不运行桌面 x86 bootstrap 于 ARM

[官方平台要求](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0003.rst)、[官方 Noetic snapshot 配置](https://raw.githubusercontent.com/osrf/docker_images/master/ros/noetic/ubuntu/focal/ros-core/Dockerfile)

## 交叉构建入口

SDK 下载结束并核验后，在新的主机 bash 中运行 bash infra/rk3588/scripts/build_legacy.sh，默认独立前缀 ../.infra/rk3588/ros1-legacy/，GNU Make 四任务，保留 Eigen/OpenCV/Ceres 版本及稀疏/LAPACK 功能。准备执行此构建，板端实际兼容性待验收

私有 GCC 9.4 的原 ipcp-unit-growth 参数已通过空翻译单元 ARM 编译，GCC 11 的参数改名在此编译器被拒绝；因此使用原 OpenCV 源码，证据见 [编译器参数核验](../infra/rk3588/reference/ros1_compiler_parameters_20261014/)。当前 ROS 1 与 ROS 2 使用独立 ABI 前缀和编译器，不混用已有 install

下载验收 ros1-fetch01 退出 0，843 个包与四个源码均通过离线重验，私有 GCC 9.4 实际运行成功，转换审计与 SHA256 见 [依赖证据](../infra/rk3588/reference/ros1_dependencies_20261014/)。该里程碑仅验收下载/校验，不将 SDK 自带库或构建前缀当作板端 VINS 已运行

主机动态库只暴露 toolchain/host-libs 内的编译器和 ARM binutils 支持库，不能将 Focal usr/lib/x86_64-linux-gnu 整目录放到 LD_LIBRARY_PATH；否则旧 libstdc++ 会抢占 Jammy CMake。cross_env.sh 自动创建这些指向已校验依赖的链接，下载目录仍忽略；在新的 bash 中 source，不继承其他 ROS/工具链环境

Noetic catkin 包还导出绝对 log4cxx/Boost 库和 /usr/include，CMake 不会自动重定位这些变量。fetch.py 对 Noetic CMake 原生库/头文件路径加 CMAKE_SYSROOT，20 个变更的前后 SHA256 单独记录在 .vins-native-cmake-relocations.json，重复执行不重复加前缀；原 .deb 与既有冻结归档不改写。Python 导出重定位账本仍独立保留
