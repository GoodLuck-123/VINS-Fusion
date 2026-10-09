"""Evaluate IMU/body-frame VINS CSV against EuRoC state ground truth using evo."""
import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np
from evo.core import metrics, sync
from evo.core.trajectory import PoseTrajectory3D


from workspace_paths import WORKSPACE_ROOT as ROOT
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".infra/matplotlib"))


def read_csv(path):
    values = []
    with path.open() as stream:
        for row in csv.reader(line for line in stream if line.strip() and not line.startswith("#")):
            values.append([float(value) for value in row[:8]])
    data = np.asarray(values)
    if data.ndim != 2 or data.shape[1] != 8 or not np.isfinite(data).all():
        raise ValueError(f"Invalid pose data: {path}")
    if np.any(np.diff(data[:, 0]) <= 0):
        raise ValueError(f"Pose timestamps are not strictly increasing: {path}")
    norms = np.linalg.norm(data[:, 4:8], axis=1)
    if np.any(norms < 0.9) or np.any(norms > 1.1):
        raise ValueError(f"Invalid quaternions: {path}")
    # Original VINS rounds quaternion components to five decimal places.
    data[:, 4:8] /= norms[:, None]
    return PoseTrajectory3D(data[:, 1:4], data[:, 4:8], data[:, 0] * 1e-9)


def save_tum(path, trajectory):
    q = trajectory.orientations_quat_wxyz
    data = np.column_stack((trajectory.timestamps, trajectory.positions_xyz, q[:, 1:4], q[:, 0]))
    np.savetxt(path, data, fmt="%.9f", header="timestamp tx ty tz qx qy qz qw")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--groundtruth", type=Path, default=ROOT / "data/euroc/MH_01_easy_groundtruth.csv")
    parser.add_argument("--max-diff", type=float, default=0.01)
    args = parser.parse_args()
    estimate_all = read_csv(args.run / "vio.csv")
    reference_all = read_csv(args.groundtruth)
    save_tum(args.run / "trajectory.tum", estimate_all)
    save_tum(args.run / "groundtruth.tum", reference_all)
    reference, estimate = sync.associate_trajectories(reference_all, estimate_all, max_diff=args.max_diff)
    rotation, translation, scale = estimate.align(reference, correct_scale=False)
    save_tum(args.run / "trajectory_aligned_se3.tum", estimate)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((reference, estimate))
    rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=1, delta_unit=metrics.Unit.frames)
    rpe.process_data((reference, estimate))
    report = {
        "evaluation": "evo; SE(3) alignment, no scale correction; IMU/body poses",
        "reference_source": str(args.groundtruth.resolve()),
        "quaternion_normalization": "Original CSV rounding normalized before evaluation",
        "max_timestamp_difference_s": args.max_diff,
        "estimated_poses": estimate_all.num_poses,
        "matched_poses": estimate.num_poses,
        "matched_estimate_fraction": estimate.num_poses / estimate_all.num_poses,
        "estimate_span_s": float(estimate_all.timestamps[-1] - estimate_all.timestamps[0]),
        "groundtruth_span_s": float(reference_all.timestamps[-1] - reference_all.timestamps[0]),
        "trajectory_length_m": float(estimate_all.path_length),
        "alignment_rotation": rotation.tolist(), "alignment_translation_m": translation.tolist(),
        "alignment_scale": float(scale),
        "ate_translation_m": ape.get_all_statistics(),
        "rpe_translation_m_one_pose_step": rpe.get_all_statistics(),
    }
    if report["matched_estimate_fraction"] < 0.95:
        raise RuntimeError("Less than 95% of estimated poses matched ground truth")
    (args.run / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(reference.positions_xyz[:, 0], reference.positions_xyz[:, 1], label="Ground truth")
    axes[0].plot(estimate.positions_xyz[:, 0], estimate.positions_xyz[:, 1], label="VINS ROS 1")
    axes[0].set(xlabel="x (m)", ylabel="y (m)", title="EuRoC MH_01_easy: SE(3) aligned")
    axes[0].axis("equal")
    axes[0].legend()
    axes[1].plot(estimate.timestamps-estimate.timestamps[0], ape.error)
    axes[1].set(xlabel="Time from first estimated pose (s)", ylabel="Position error (m)",
                title=f"ATE RMSE: {report['ate_translation_m']['rmse']:.4f} m")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(args.run / "trajectory.png", dpi=180)
    plt.close(fig)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
