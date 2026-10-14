"""Prepare and validate the missing Fast DDS runtime through the fixed remote tool."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess

REPO = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--target', default='firefly@10.106.0.220')
    args = parser.parse_args()
    phase = Path(os.environ['VINS_PHASE_DIRECTORY'])
    subprocess.run(['/usr/bin/python3', str(REPO / 'infra/dependencies/fetch.py')], check=True)
    subprocess.run(['/usr/bin/python3', str(REPO / 'infra/rk3588/scripts/prepare_fastrtps_runtime.py')], check=True)
    script = phase / 'probe.sh'
    # One explicit, shell-quoted runtime argument; remote tools do not forward host env.
    original = (REPO / 'infra/rk3588/scripts/fastrtps_runtime_smoke.sh').read_text()
    script.write_text('export VINS_ARM_VERIFIED_RUNTIME=' + shlex.quote(args.runtime) + '\n' + original)
    subprocess.run([str(REPO.parent / '.infra/bin/vins-remote'), args.target,
                    str(REPO.parent / '.infra/rk3588/fastrtps-payload'), '--run', str(script),
                    '--output', str(phase / 'board'), '--timeout', '240'], check=True)


if __name__ == '__main__':
    main()
