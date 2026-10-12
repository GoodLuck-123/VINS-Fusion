# Camera calibration examples

ROS 2 branch examples; activate the environment described in [the setup guide](../../docs/04_UBUNTU22_ROS2_SETUP.md) first. The desktop baseline builds this tool with GUI support disabled; interactive calibration has not been validated

Check available parameters:

```bash
ros2 run camera_models Calibrations --help
```

Calibrate a pinhole model:

```bash
# From the repository root, after activating the ROS 2 environment:
cd camera_models/camera_calib_example
ros2 run camera_models Calibrations -w 12 -h 8 -s 80 -i calibrationdata --camera-model pinhole
```

Calibrate a MEI model:

```bash
# In camera_models/camera_calib_example:
ros2 run camera_models Calibrations -w 12 -h 8 -s 80 -i calibrationdata --camera-model mei
```
