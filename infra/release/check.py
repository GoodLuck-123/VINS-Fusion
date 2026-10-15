"""Check the release using the existing runtime lifecycle probe, without replaying data."""
import argparse
import os
from pathlib import Path
import platform
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New log directory')
    args = parser.parse_args()
    if platform.machine() != 'aarch64':
        parser.error('This install package is for an ARM64 board, not the x86 host')
    root = Path(os.environ['VINS_INSTALL_ROOT'])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'logs').mkdir()
    env = dict(os.environ, VINS_REMOTE_ROOT=str(output), VINS_REMOTE_PAYLOAD=str(root))
    command = ['bash', str(root / 'scripts/smoke.sh')] if (root / 'runtime/python38').exists() else [
        'python3', str(root / 'scripts/smoke.py')]
    with (output / 'console.log').open('w') as log:
        code = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    print('Runtime check exit:', code, '; logs:', output)
    if code:
        print((output / 'console.log').read_text())
    raise SystemExit(code)


if __name__ == '__main__':
    main()
