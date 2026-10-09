"""Check actual loaded libraries rather than trusting package version labels."""
import json
import os
from pathlib import Path
import re
import subprocess


from workspace_paths import WORKSPACE_ROOT as ROOT
LEGACY = ROOT / ".infra/legacy"
targets = {
    "vins_node": ROOT / ".infra/vins_ws/devel/lib/vins/vins_node",
    "loop_fusion_node": ROOT / ".infra/vins_ws/devel/lib/loop_fusion/loop_fusion_node",
    "global_fusion_node": ROOT / ".infra/vins_ws/devel/lib/global_fusion/global_fusion_node",
    "cv_bridge": ROOT / ".infra/bridge_ws/devel/lib/libcv_bridge.so",
}
report = {"targets": {}, "legacy_prefix": str(LEGACY), "opencv_version": "4.2.0", "ceres_version": "1.14.0"}
for name, target in targets.items():
    if not target.is_file():
        raise RuntimeError(f"Missing build target: {target}")
    output = subprocess.check_output(["ldd", str(target)], text=True)
    if "not found" in output:
        raise RuntimeError(f"Unresolved libraries for {name}:\n{output}")
    interesting = [line.strip() for line in output.splitlines()
                   if re.search(r"libopencv|libceres|libcv_bridge", line)]
    for line in interesting:
        if "libopencv" in line or "libceres" in line:
            if str(LEGACY / "lib") not in line:
                raise RuntimeError(f"Unexpected vision/solver library: {line}")
        if "libopencv" in line and ".so.4.2 " not in line:
            raise RuntimeError(f"Mixed OpenCV version: {line}")
    if name in ("vins_node", "cv_bridge") and not any("libopencv" in x for x in interesting):
        raise RuntimeError(f"Expected OpenCV dependencies missing: {name}")
    report["targets"][name] = interesting
for workspace in ("bridge_ws", "vins_ws"):
    cache = (ROOT / f".infra/{workspace}/build/CMakeCache.txt").read_text()
    expected = rf"^OpenCV_DIR:[^=]+={re.escape(str(LEGACY / 'lib/cmake/opencv4'))}$"
    if not re.search(expected, cache, re.M):
        raise RuntimeError(f"Unexpected OpenCV configuration in {workspace}")
report["native_python"] = subprocess.check_output(["python", "--version"], text=True).strip()
report["compiler"] = subprocess.check_output([os.environ.get("CXX", "c++"), "--version"], text=True).splitlines()[0]
report["source_commit"] = subprocess.check_output(
    ["git", "-C", str(ROOT / "VINS-Fusion"), "rev-parse", "HEAD"], text=True).strip()
report["source_modified"] = bool(subprocess.check_output(
    ["git", "-C", str(ROOT / "VINS-Fusion"), "status", "--porcelain", "--",
     "camera_models", "vins_estimator", "loop_fusion", "global_fusion", "config", "support_files",
     ":(exclude)**/*.md", ":(exclude)**/readme.txt", ":(exclude)support_files/paper_bib.txt"],
    text=True).strip())
if report["source_modified"]:
    raise RuntimeError("Original source working tree has modifications")
report["ceres_shared_library"] = str((LEGACY / "lib/libceres.so.1").resolve())
if not report["ceres_shared_library"].endswith("libceres.so.1.14.0"):
    raise RuntimeError("Unexpected Ceres shared library version")
destination = ROOT / "results/ros1/native_environment.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
