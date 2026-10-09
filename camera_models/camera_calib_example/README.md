# Camera calibration examples

Check available parameters:

```bash
rosrun camera_models Calibrations --help
```

Calibrate a pinhole model:

```bash
rosrun camera_models Calibrations -w 12 -h 8 -s 80 -i calibrationdata --camera-model pinhole
```

Calibrate a MEI model:

```bash
rosrun camera_models Calibrations -w 12 -h 8 -s 80 -i calibrationdata --camera-model mei
```
