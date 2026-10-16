#!/usr/bin/env bash
set -euo pipefail
candidate="$VINS_REMOTE_WORKSPACE/validation/shutdown-fix/install"
mkdir -p "$(dirname "$candidate")"
if ! test -d "$candidate"; then cp -a "$VINS_REMOTE_WORKSPACE/releases/ros1-v0.2/install/." "$candidate"; fi
cp "$VINS_REMOTE_PAYLOAD/vins_node" "$candidate/bin/vins_node"
chmod 755 "$candidate/bin/vins_node"
cp "$VINS_REMOTE_PAYLOAD/libvins_lib.so" "$candidate/runtime/lib/libvins_lib.so"
/usr/bin/python3 -I - "$candidate" "$VINS_REMOTE_PAYLOAD/source.json" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);source=json.loads(Path(sys.argv[2]).read_text())
(root/'share/provenance/build_source.json').write_text(json.dumps(source,indent=2)+'\n')
p=root/'release.json';metadata=json.loads(p.read_text());metadata.update(version='v0.2.1-candidate',source=source);p.write_text(json.dumps(metadata,indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts))
PY
"$candidate/bin/check" --arc --lib --sha --json "$VINS_REMOTE_ROOT/logs/preflight.json"
exec /usr/bin/python3 -I "$VINS_REMOTE_PAYLOAD/shutdown_edges.py" "$candidate" \
  "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" "$VINS_REMOTE_ROOT/logs/edges"
