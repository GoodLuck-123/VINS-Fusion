"""Record the physical Ubuntu host and toolchain context without changing settings."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
report = {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          'kernel': platform.release(), 'architecture': platform.machine(),
          'wsl': 'microsoft' in platform.release().lower(),
          'commands': {}}
for command in (['lscpu'], ['uname', '-a'], ['df', '-h', '.'], ['free', '-h'],
                ['git', 'status', '--short', '--branch'], ['git', 'rev-parse', 'HEAD'],
                ['uv', '--version'], ['systemd-detect-virt']):
    result = subprocess.run(command, capture_output=True, text=True)
    report['commands'][' '.join(command)] = {'exit_code': result.returncode,
                                            'stdout': result.stdout, 'stderr': result.stderr}
report['os_release'] = Path('/etc/os-release').read_text()
report['cpu_governors'] = {str(p): p.read_text().strip() for p in
                          sorted(Path('/sys/devices/system/cpu').glob('cpu*/cpufreq/scaling_governor'))}
report['space_free_bytes'] = shutil.disk_usage('.').free
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open('x') as stream:
    stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(args.output)
