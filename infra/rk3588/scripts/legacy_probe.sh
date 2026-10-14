#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/lib"
python3 - <<'CHECK'
import hashlib,json,os,pathlib
root=pathlib.Path(os.environ['VINS_REMOTE_PAYLOAD'])
for name,sha in json.loads((root/'files.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha, name
CHECK
ldd "$VINS_REMOTE_PAYLOAD/legacy_smoke" > "$VINS_REMOTE_ROOT/logs/ldd.txt"
if grep -q 'not found' "$VINS_REMOTE_ROOT/logs/ldd.txt"; then exit 1; fi
"$VINS_REMOTE_PAYLOAD/legacy_smoke" > "$VINS_REMOTE_ROOT/logs/legacy.log" 2>&1
grep -q 'ARM_LEGACY_OK opencv=4.2.0 ceres=1.14.0' "$VINS_REMOTE_ROOT/logs/legacy.log"
