# 前端 copy/share 一致性探针

先将 local_probes 归档中的 native_image_probe.cpp 与 native_shared_probe.cpp 复制到仓库 `.local-tests/`，再将本目录三个源码文件复制到同一目录；CMake 同时声明三类探针，配置时需齐全的源文件。普通 uv shell 运行 `uv run --project infra/desktop --locked python .local-tests/prepare_feature_probe.py`，从固定 SHA256 的 MH_01_easy 提取前十对原始灰度图像并写测试配置。默认新目录为 `../results/ubuntu22-reproduction/feature-probe01`，已存在时拒绝覆盖；同机补测另立目录或复用已核验的输入文件，不改历史结果

新 ROS 2 shell source 专用环境，用 Debug/ASan 编译 native_feature_probe；CMake 明确 find_package OpenCV 4.2.0、Ceres 1.14.0，不混入系统库。按以下形式分别运行单目和双目配置：

```bash
ASAN_OPTIONS=detect_leaks=0 ../.infra/build/native-probes/native_feature_probe ../results/ubuntu22-reproduction/feature-probe01/euroc_mono_imu_config.yaml ../results/ubuntu22-reproduction/feature-probe01/frames.txt
ASAN_OPTIONS=detect_leaks=0 ../.infra/build/native-probes/native_feature_probe ../results/ubuntu22-reproduction/feature-probe01/euroc_stereo_imu_config.yaml ../results/ubuntu22-reproduction/feature-probe01/frames.txt
```

保持全部算法参数，两个独立 FeatureTracker 分别消费 copy/share 图像，逐帧核验 IDs、相机编号和七维观测，绝对容差 1e-12；share 持有上一左图 owner。此局部测试没有 IMU 预测，不等于完整 VIO 或全程序 ASan。首次局部编译缺 Ceres 头路径的失败日志也保留，VINS 源码未改
