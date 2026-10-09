#!/usr/bin/env bash
# Resolve the tracked infra/desktop/scripts directory, even via workspace aliases.
VINS_DESKTOP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
VINS_REPO_DIR="$(cd "$VINS_DESKTOP_DIR/../.." && pwd)"
VINS_WORKSPACE_DIR="$(cd "$VINS_REPO_DIR/.." && pwd)"
