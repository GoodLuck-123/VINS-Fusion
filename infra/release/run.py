"""Run a deployed release and collect logs; upload only a small request, not install again."""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from remote_settings import add_options, load, remote_path, EVENT_SHELL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', help='Default from vins-remote config')
    parser.add_argument('--ros', choices=['ros1', 'ros2'], default='ros1')
    parser.add_argument('--version', help='Explicit version; default uses selected workspace/install')
    parser.add_argument('--bag', help='Existing absolute board path; omit to perform a no-data runtime check')
    parser.add_argument('--output', type=Path, required=True, help='New host results directory')
    add_options(parser)
    args = parser.parse_args()
    if args.version and not re.fullmatch(r'v[0-9]+\.[0-9]+(?:\.[0-9]+)?', args.version):
        parser.error('Invalid version')
    if args.bag and (args.ros != 'ros1' or not Path(args.bag).is_absolute()):
        parser.error('--bag supports ROS 1 EuRoC stereo input at an absolute board path')
    tool, common, settings = load(args)
    target = args.target or settings['target']
    script = '#!/usr/bin/env bash\nset -euo pipefail\n' + EVENT_SHELL
    script += 'workspace=' + remote_path(settings['root']) + '\n'
    if args.version or args.ros == 'ros2':
        script += 'install="$workspace/releases/' + args.ros + '-' + (args.version or 'v0.1') + '/install"\n'
    else:
        script += 'install="$workspace/install"\n'
    script += 'test -x "$install/bin/vins" || { echo "Missing selected install: $install" >&2; exit 2; }\n'
    script += 'event INSTALL_SELECTED "$install"\n'
    if args.bag:
        script += 'event REPLAY_STARTED "EuRoC stereo + IMU replay"\n'
        script += '"$install/bin/vins" euroc ' + shlex.quote(args.bag) + ' "$VINS_REMOTE_ROOT/logs/experiment"\n'
        script += 'event REPLAY_FINISHED "Runner returned; inspect run.json and per-process exits"\n'
    else:
        script += 'event CHECK_STARTED "Checking deployed runtime without data"\n'
        script += '"$install/bin/vins" check "$VINS_REMOTE_ROOT/logs/runtime-check"\n'
        script += 'event CHECK_PASSED "Runtime lifecycle probe passed; inspect process exits"\n'
    with tempfile.TemporaryDirectory(prefix='vins-run-') as temp:
        request = Path(temp) / 'request.txt'
        request.write_text('No install upload; use the existing versioned board release\n')
        path = Path(temp) / 'run.sh'
        path.write_text(script)
        result = subprocess.run([str(tool), target, str(request), '--run', str(path),
                                 '--output', str(args.output), '--timeout', '3600' if args.bag else '180', *common])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
