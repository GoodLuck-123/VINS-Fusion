# 重建局部探针

在仓库根目录将本目录四个源码文件复制到 `.local-tests/`，source `infra/desktop/scripts/ros2_env.sh`，以该目录为 CMake source，保持 Debug、ASan 和断言开启；不要把 `.local-tests/` 当作 clone 已包含的运行依赖

```bash
mkdir -p .local-tests
cp infra/desktop/comparison_reference/native_ubuntu22_20261013/local_probes/{native_image_probe.cpp,native_shared_probe.cpp,native_component_probe.py,CMakeLists.txt} .local-tests/
source infra/desktop/scripts/ros2_env.sh
cmake -S .local-tests -B ../.infra/build/native-probes -G Ninja -DCMAKE_BUILD_TYPE=Debug -DOpenCV_DIR="$OpenCV_DIR" -DPython3_EXECUTABLE="$CONDA_PREFIX/bin/python"
cmake --build ../.infra/build/native-probes -j2
ASAN_OPTIONS=detect_leaks=0 ../.infra/build/native-probes/native_image_probe
ASAN_OPTIONS=detect_leaks=0 ../.infra/build/native-probes/native_shared_probe memfd
ASAN_OPTIONS=detect_leaks=0 ../.infra/build/native-probes/native_shared_probe vgem
python .local-tests/native_component_probe.py --output ../results/ubuntu22-reproduction/新探针目录
```

共享压力测试在启动线程前 fork，两个进程使用 4 槽位和 1000 帧，验证 padding 输入复制、上一帧 owner、代次、像素摘要与归还。VGEM 必须先核实当前设备；源码中的 card0 是本次真实核验节点

组件探针分别以 `VINS_RMW_IMPLEMENTATION=rmw_fastrtps_cpp` 与 `rmw_cyclonedds_cpp` source 后执行，新输出目录拒绝覆盖。每种 RMW 三轮单目与双目加载/卸载，另核验重复实例和无效配置拒绝

这是局部 ASan，依赖库未全部插桩、未启用 LeakSanitizer，不能代替全程序或长期泄漏检查
