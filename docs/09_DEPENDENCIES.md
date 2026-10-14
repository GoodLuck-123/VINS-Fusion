# 依赖下载与版本锁定

更新日期：2026-10-14

普通 git clone 只取得源码、依赖锁和目录占位，不下载 OpenCV、Ceres 或 SDK。无需 Git submodule；联网的 Linux x86_64 主机在仓库根执行一个命令：

```bash
python3 infra/dependencies/fetch.py
```

需要系统 Python 3、curl、dpkg-deb；不需要 sudo、不安装系统包、不在板上下载。下载后先检查 SHA256，再解包；中断可重跑同一命令，缓存也重新校验。现有 SDK 或源码版本与锁不符时停止，不覆盖或偷偷升级

## 目录与锁

| 内容 | 固定版本 / 范围 | 下载后的目录 |
| --- | --- | --- |
| OpenCV | 4.2.0 | dependencies/sources/opencv/4.2.0 |
| Ceres | 1.14.0 | dependencies/sources/ceres/1.14.0 |
| Eigen | 3.3.9 | dependencies/sources/eigen/3.3.9 |
| ROS 1 cv_bridge 源码 | vision_opencv 1.16.2 | dependencies/sources/cv_bridge_ros1/1.16.2 |
| ROS 2 cv_bridge 源码 | vision_opencv 3.2.1 | dependencies/sources/cv_bridge_ros2/3.2.1 |
| x86_64 → aarch64 工具链 | GCC 11.4.0，25 个包 | dependencies/toolchain/root |
| ARM ROS 2 sysroot | Ubuntu Jammy / Humble，807 个包 | dependencies/sysroots/ros2-humble/root |

源码锁为 `dependencies/sources.lock.json`；工具链与目标包锁为 `dependencies/locks/*.json`，记录具体版本、架构、URL 和 SHA256。包锁来自已经验证签名的 Ubuntu/ROS apt 索引，与 [交叉 SDK 验收快照](../infra/rk3588/reference/cross_sdk_20261014/) 的全部 832 个包哈希一致；普通重建直接按锁下载，不重新在线解依赖

`dependencies/cache/` 保存压缩包；源码、工具链与 sysroot 目录只跟踪 `.gitkeep`，下载和解包内容由局部 `.gitignore` 排除，不进入 commit。构建目录、安装前缀仍在 `../.infra/`，数据和完整日志仍在 `../data/`、`../results/`；不迁移或覆盖旧桌面环境及冻结 SDK

只取通用源码时使用 `--sources-only`；这不建立桌面 ROS 环境，也不代替第 02/04 份文档的原生锁。当前包锁是 ARM ROS 2 SDK，ROS 1 板端 SDK 后续需单独锁定，不能拿 Humble 的库运行 ROS 1

ARM sysroot 解包后，将包内绝对符号链接改为目标根目录内的相对链接，避免从 x86 主机查找目标 libm 等库；转换记录保存在 sysroot 根目录的 `.vins-sysroot-links.json`。包版本与归档 SHA256 不变，不执行 postinst 或修改主机系统；改正之前创建的统一 SDK 后必须完整重建库，不能复用旧链接产物

## 复用缓存与离线重建

已有下载可按哈希复用，路径参数可重复；不会移动或修改旧缓存：

```bash
python3 infra/dependencies/fetch.py --cache-from ../.infra/downloads
python3 infra/dependencies/fetch.py --offline --cache-from /完整缓存目录
```

`--offline` 禁止联网，缺文件或哈希不符即失败。只复制源码目录或 SDK 的 ready 文件不能替代下载校验；锁中的归档必须在缓存中。源码可用于开发修改，完成标记只表示原始解包版本，不是修改后的源码完整性证明

锁定的是下载，不是已编译的 VINS。OpenCV/Ceres/cv_bridge 仍需为 ARM 重建；SDK 自带的 OpenCV 4.5.4/cv_bridge 不是最终 VINS 参照。完成 ARM ELF、运行时库与板端验收后才部署实验，入口见 [第 08 份文档](08_RK3588_WORKFLOW.md)

交叉构建先进入新的 bash，再 `source infra/rk3588/scripts/cross_env.sh`；同一环境用于 CMake 配置和编译。该环境设置主机编译器的动态库目录及目标库/pkg-config 查找目录；CMake 使用 `infra/rk3588/cmake/aarch64.cmake`，不 source 桌面或板端 ROS 环境

需要升级依赖时显式更新锁并重新验收，保留旧锁和历史证据。上游若删除固定版本，下载应明确失败；不回退到 latest 或未经校验的镜像

本机已验证五个源码包、832 个包锁与原签名 SDK 哈希一致；完整下载/解包、离线重跑、新缓存实际下载 Eigen、损坏缓存拒绝均通过。新路径 CMake 交叉编译的 ARM 小程序在板上正常退出，运行时库齐全。首次链接及缺失 payload 的启动失败单独保留，见 [本阶段证据](../infra/rk3588/reference/dependencies_20261014/)；没有将此验证称为 VINS 验收

Humble 预编译消息的 CMake 导出另有字面 libpython 绝对路径；下载入口为它加 CMAKE_SYSROOT，避免消费者在主机根目录找 ARM 库。变更文件的前后 SHA256 保存为 `.vins-python-cmake-relocations.json`，原包锁和二进制不变，既有统一 SDK 可离线重跑入口应用修正
