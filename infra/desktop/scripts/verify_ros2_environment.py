"""Reject cross-environment native paths in loaded libraries and build commands."""
import hashlib
import json
from pathlib import Path
import subprocess

from workspace_paths import WORKSPACE_ROOT as ROOT

workspace = ROOT / ".infra/ros2_ws"
legacy = ROOT / ".infra/legacy_ros2"
targets = {"vins": workspace / "install/lib/vins/vins_node",
           "loop_fusion": workspace / "install/lib/loop_fusion/loop_fusion_node",
           "global_fusion": workspace / "install/lib/global_fusion/global_fusion_node",
           "cv_bridge": workspace / "install/lib/libcv_bridge.so"}
if (workspace / "install/lib/libvins_component.so").exists():
    targets["vins_component"] = workspace / "install/lib/libvins_component.so"
if (workspace / "install/lib/libvins_euroc_component.so").exists():
    targets["euroc_player"] = workspace / "install/lib/libvins_euroc_component.so"
if (workspace / "install/lib/vins/euroc_player_node").exists():
    targets["euroc_player_node"] = workspace / "install/lib/vins/euroc_player_node"
forbidden = ("/.infra/ros1/", "/.infra/legacy/", "/.infra/bridge_ws/")
report = {"opencv": "4.2.0", "ceres": "1.14.0", "targets": {}}
for name, binary in targets.items():
    text = subprocess.check_output(["ldd", str(binary)], text=True)
    if "not found" in text or any(path in text for path in forbidden):
        raise RuntimeError(f"Unresolved or cross-environment library for {name}:\n{text}")
    for line in text.splitlines():
        if "libopencv" in line and (str(legacy / "lib") not in line or ".so.4.2 " not in line):
            raise RuntimeError(f"Mixed OpenCV: {line}")
        if "libceres" in line and str(legacy / "lib") not in line:
            raise RuntimeError(f"Mixed Ceres: {line}")
        if "libcrypto.so" in line and str(ROOT / ".infra/ros2/lib") not in line:
            raise RuntimeError(f"Mixed OpenSSL: {line}")
    report["targets"][name] = {"ldd": text.splitlines(), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
for path in workspace.glob("build/*/compile_commands.json"):
    if any(prefix in path.read_text() for prefix in forbidden):
        raise RuntimeError(f"Cross-environment compilation: {path}")
if not (legacy / "lib/libceres.so.1").resolve().name.endswith("1.14.0"):
    raise RuntimeError("Unexpected Ceres version")
destination = ROOT / "results/ros2/native_environment.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2) + "\n")
print("ROS 2 loaded libraries and compilation paths are isolated; OpenCV 4.2.0 / Ceres 1.14.0 verified.")
