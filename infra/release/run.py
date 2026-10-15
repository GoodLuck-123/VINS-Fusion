"""Run a deployed release and collect logs; upload only a small request, not install again."""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target')
    parser.add_argument('--ros', choices=['ros1', 'ros2'], default='ros1')
    parser.add_argument('--version', default='v0.1')
    parser.add_argument('--bag', help='Existing absolute board path; omit to perform a no-data runtime check')
    parser.add_argument('--output', type=Path, required=True, help='New host results directory')
    parser.add_argument('--tool', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'v[0-9]+\.[0-9]+(?:\.[0-9]+)?', args.version):
        parser.error('Invalid version')
    if args.bag and (args.ros != 'ros1' or not Path(args.bag).is_absolute()):
        parser.error('--bag supports ROS 1 EuRoC stereo input at an absolute board path')
    here = Path(__file__).resolve().parent
    tool = args.tool or (here / 'vins-remote' if (here / 'vins-remote').exists()
                         else here.parents[2] / '.infra/bin/vins-remote')
    script = '#!/usr/bin/env bash\nset -euo pipefail\n'
    script += 'install="$HOME/vins-workspace/releases/' + args.ros + '-' + args.version + '/install"\n'
    if args.bag:
        script += '"$install/bin/vins" euroc ' + shlex.quote(args.bag) + ' "$VINS_REMOTE_ROOT/logs/experiment"\n'
    else:
        script += '"$install/bin/vins" check "$VINS_REMOTE_ROOT/logs/runtime-check"\n'
    with tempfile.TemporaryDirectory(prefix='vins-run-') as temp:
        request = Path(temp) / 'request.txt'
        request.write_text('No install upload; use the existing versioned board release\n')
        path = Path(temp) / 'run.sh'
        path.write_text(script)
        result = subprocess.run([str(tool), args.target, str(request), '--run', str(path),
                                 '--output', str(args.output), '--timeout', '3600' if args.bag else '180'])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
