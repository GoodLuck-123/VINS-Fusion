"""Locate the checkout and its parent runtime workspace independently of aliases."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent
