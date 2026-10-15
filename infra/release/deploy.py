"""Deploy one complete install archive with the existing scp/run/collect tool."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='USER@HOST; passwordless SSH must already work')
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, help='New host deployment log directory')
    parser.add_argument('--tool', type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    # Inspect only our generated archive format; never extract untrusted paths.
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            p = Path(member.name)
            if p.is_absolute() or '..' in p.parts or p.parts[0] != 'install' or member.issym() or member.islnk():
                parser.error('Unexpected archive member: ' + member.name)
        metadata = json.load(tar.extractfile('install/release.json'))
    ros, version = metadata['ros'], metadata['version']
    import re
    if ros not in ('ros1', 'ros2') or not re.fullmatch(r'v[0-9]+\.[0-9]+(?:\.[0-9]+)?', version):
        parser.error('Unexpected release metadata')
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_name(archive.name + '.sha256')
    if not checksum.is_file() or checksum.read_text().split()[0] != sha:
        parser.error('Archive SHA256 does not match its .sha256 companion')
    here = Path(__file__).resolve().parent
    tool = args.tool or (here / 'vins-remote' if (here / 'vins-remote').exists()
                         else here.parents[2] / '.infra/bin/vins-remote')
    output = args.output or archive.parent / ('deploy-' + time.strftime('%Y%m%d-%H%M%S'))
    # Keep the accepted install immutable. Stage on the same filesystem and
    # refuse replacement, including repeat deployments of this version.
    script = '''#!/usr/bin/env bash
set -euo pipefail
printf '%s  %s\\n' EXPECTED "$VINS_REMOTE_PAYLOAD" | sha256sum -c -
release="$HOME/vins-workspace/releases/RELEASE"
mkdir -p "$release"
if test -e "$release/install"; then echo "Already installed: $release/install; refusing overwrite" >&2; exit 2; fi
stage=$(mktemp -d "$release/.unpack-XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
tar -xzf "$VINS_REMOTE_PAYLOAD" -C "$stage"
(cd "$stage/install" && sha256sum --quiet -c SHA256SUMS)
mv -T -n "$stage/install" "$release/install"
test ! -e "$stage/install" || { echo 'Another deployment won; refusing overwrite' >&2; exit 2; }
printf '%s\\n' "$release/install" > "$VINS_REMOTE_ROOT/logs/install_path.txt"
cp "$release/install/release.json" "$VINS_REMOTE_ROOT/logs/release.json"
"$release/install/bin/vins" check "$VINS_REMOTE_ROOT/logs/runtime-check"
'''.replace('EXPECTED', shlex.quote(sha)).replace('RELEASE', ros + '-' + version)
    with tempfile.TemporaryDirectory(prefix='vins-deploy-') as temp:
        path = Path(temp) / 'deploy.sh'
        path.write_text(script)
        result = subprocess.run([str(tool), args.target, str(archive), '--run', str(path),
                                 '--output', str(output), '--timeout', '300'])
    print('Board install:', '~/vins-workspace/releases/' + ros + '-' + version + '/install')
    print('Host logs:', output)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
