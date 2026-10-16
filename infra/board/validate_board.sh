#!/usr/bin/env bash
set -euo pipefail
candidate="$VINS_REMOTE_WORKSPACE/validation/v02/install"
mkdir -p "$(dirname "$candidate")"
if ! test -d "$candidate"; then cp -a "$VINS_REMOTE_WORKSPACE/install/." "$candidate"; fi
/usr/bin/python3 "$VINS_REMOTE_PAYLOAD/install.py" "$candidate"
# A development-only copy; never alter the selected or frozen install.
/usr/bin/python3 - "$candidate" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);p=root/'release.json';data=json.loads(p.read_text());data['version']='v0.2-candidate';p.write_text(json.dumps(data,indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts))
PY
export VINS_V02_INSTALL="$candidate"
source "$candidate/env.sh"
# Explicitly run from an initialized ROS shell: the CLI's -I entry must ignore
# inherited PYTHONHOME=private3.8 when launching the system Python 3.10.
check --arc --lib --sha --dir --output "$VINS_REMOTE_ROOT/logs/prospective" --json "$VINS_REMOTE_ROOT/logs/preflight.json"
check --config --bag "$VINS_REMOTE_WORKSPACE/projects/vins/data/euroc/MH_01_easy.bag" --output "$VINS_REMOTE_ROOT/logs/prospective" --json "$VINS_REMOTE_ROOT/logs/euroc.json"
python3 "$VINS_REMOTE_PAYLOAD/fixtures.py" "$VINS_REMOTE_ROOT/logs/fixtures"
/usr/bin/python3 -I "$VINS_REMOTE_PAYLOAD/verify_fixtures.py" "$candidate" "$VINS_REMOTE_ROOT/logs/fixtures" "$VINS_REMOTE_ROOT/logs"
echo '[CHECKS_PASSED] Independent checks and negative bag fixtures passed'
