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
from remote_settings import add_options, load, remote_path, EVENT_SHELL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', help='[USER@HOST] ARCHIVE; default host from vins-remote config')
    parser.add_argument('--output', type=Path, help='New host deployment log directory')
    add_options(parser)
    args = parser.parse_args()
    tool, common, settings = load(args)
    if len(args.paths) == 1:
        target, archive_path = settings['target'], args.paths[0]
    elif len(args.paths) == 2:
        target, archive_path = args.paths
    else:
        parser.error('Use [USER@HOST] ARCHIVE')
    archive = Path(archive_path).resolve()
    # Inspect only our generated archive format; never extract untrusted paths.
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            p = Path(member.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != 'install' or not (member.isfile() or member.isdir()):
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
    output = args.output or archive.parent / ('deploy-' + time.strftime('%Y%m%d-%H%M%S'))
    # Keep the accepted install immutable. Stage on the same filesystem and
    # refuse replacement, including repeat deployments of this version.
    script = '''#!/usr/bin/env bash
set -euo pipefail
EVENT_SHELL
workspace=WORKSPACE
event ARCHIVE_VERIFY 'Verifying uploaded archive'
printf '%s  %s\\n' EXPECTED "$VINS_REMOTE_PAYLOAD" | sha256sum -c -
event ARCHIVE_VERIFIED 'Archive SHA256 matched'
release="$workspace/releases/RELEASE"
mkdir -p "$release"
if test -e "$release/install"; then echo "Already installed: $release/install; refusing overwrite" >&2; exit 2; fi
stage=$(mktemp -d "$release/.unpack-XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
event UNPACK_STARTED 'Extracting install package'
if tar -xzf "$VINS_REMOTE_PAYLOAD" -C "$stage" 2>"$VINS_REMOTE_ROOT/logs/unpack.stderr"; then
  if test -s "$VINS_REMOTE_ROOT/logs/unpack.stderr"; then
    event UNPACK_NOTICE "tar diagnostics saved to unpack.stderr ($(wc -l < "$VINS_REMOTE_ROOT/logs/unpack.stderr") lines)"
  fi
else
  code=$?
  event UNPACK_FAILED 'See unpack.stderr for extraction failure'
  cat "$VINS_REMOTE_ROOT/logs/unpack.stderr" >&2
  exit "$code"
fi
(cd "$stage/install" && sha256sum --quiet -c SHA256SUMS)
event PACKAGE_VERIFIED 'All package files matched'
mv -T -n "$stage/install" "$release/install"
test ! -e "$stage/install" || { echo 'Another deployment won; refusing overwrite' >&2; exit 2; }
printf '%s\\n' "$release/install" > "$VINS_REMOTE_ROOT/logs/install_path.txt"
cp "$release/install/release.json" "$VINS_REMOTE_ROOT/logs/release.json"
event CHECK_STARTED 'Checking imports, linkage and node readiness'
"$release/install/bin/vins" check "$VINS_REMOTE_ROOT/logs/runtime-check"
event CHECK_PASSED 'Runtime lifecycle probe passed; inspect recorded process exits'
if test ROS = ros1; then
  link="$workspace/install"
  if test -e "$link" && ! test -L "$link"; then echo "Refusing to replace a real install directory: $link" >&2; exit 2; fi
  next="$workspace/.install-$(basename "$VINS_REMOTE_ROOT")"
  ln -s "$release/install" "$next"
  mv -Tf "$next" "$link"
  event INSTALL_SELECTED "$link"
fi
'''.replace('EVENT_SHELL', EVENT_SHELL).replace('WORKSPACE', remote_path(settings['root'])).replace('EXPECTED', shlex.quote(sha)).replace('RELEASE', ros + '-' + version).replace('ROS', shlex.quote(ros))
    with tempfile.TemporaryDirectory(prefix='vins-deploy-') as temp:
        path = Path(temp) / 'deploy.sh'
        path.write_text(script)
        result = subprocess.run([str(tool), target, str(archive), '--run', str(path),
                                 '--output', str(output), '--timeout', '300', *common])
    print('Board install:', settings['root'] + '/releases/' + ros + '-' + version + '/install')
    print('Host logs:', output)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
