"""Restore workspace aliases after cloning the repository into VINS-Fusion/."""
from workspace_paths import REPO_ROOT, WORKSPACE_ROOT

DESKTOP = REPO_ROOT / "infra/desktop"
targets = {name: DESKTOP / name for name in (
    "scripts", "environment-ros1.yml", "ros1-linux-64.lock", "pyproject.toml",
    "uv.lock", "baseline-assets.sha256", "baseline_reference", ".gitignore",
)}
targets.update({name: REPO_ROOT / "docs" / name for name in (
    "RK3588_DEPLOYMENT_TASK_BRIEF.md", "UBUNTU22_ROS1_BASELINE_SETUP.md",
    "BASELINE_REFERENCE_REPORT.md",
)})
for name, target in targets.items():
    alias = WORKSPACE_ROOT / name
    if alias.exists() or alias.is_symlink():
        if alias.is_symlink() and alias.resolve() == target.resolve():
            continue
        raise RuntimeError(f"Preserving existing path; resolve the conflict before retrying: {alias}")
    alias.symlink_to(target.relative_to(WORKSPACE_ROOT), target_is_directory=target.is_dir())
    print(f"{alias} -> {target}")
