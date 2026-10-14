"""Read-only board inventory; download and installation are host-side steps."""
import gzip
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time

from probe_hardware_metrics import collect, read


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        return dict(exit_code=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(error=str(error))


result = dict(timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              machine=platform.machine(), kernel=platform.release(),
              os_release=read('/etc/os-release'),
              model=read('/sys/firmware/devicetree/base/model'),
              cpu=command(['lscpu']), memory=read('/proc/meminfo'),
              mounts=read('/proc/mounts'), disk=command(['df', '-h', '/', '/home']),
              tools={name: shutil.which(name) for name in ('gcc', 'g++', 'cmake', 'python3', 'perf',
                                                          'trace-cmd', 'gatord', 'systemd-run')},
              hardware=collect(),
              thermal={str(p.parent): {'type': read(p.parent / 'type'), 'temp': read(p)}
                       for p in Path('/sys/class/thermal').glob('thermal_zone*/temp')},
              cpufreq={str(p): {n: read(p / n) for n in ('affected_cpus', 'scaling_governor',
                                                        'scaling_cur_freq', 'scaling_max_freq')}
                       for p in Path('/sys/devices/system/cpu/cpufreq').glob('policy*')},
              devfreq={str(p): {n: read(p / n) for n in ('name', 'governor', 'cur_freq', 'available_frequencies')}
                       for p in Path('/sys/class/devfreq').glob('*')},
              dma_heaps=[str(p) for p in Path('/dev/dma_heap').glob('*')],
              debugfs=command(['sudo', '-n', 'find', '/sys/kernel/debug', '-maxdepth', '2', '-type', 'd']),
              sudo_noninteractive=command(['sudo', '-n', 'true']))
packages = command(['dpkg-query', '-W', '-f=${Package} ${Version}\n'])
result['packages'] = [line for line in packages.get('stdout', '').splitlines()
                      if line.split()[0].startswith(('ros-', 'libceres', 'libopencv', 'libeigen', 'gcc',
                                                     'cmake', 'python3', 'libc6', 'libstdc++'))]
try:
    config = gzip.open('/proc/config.gz', 'rt').read()
    result['kernel_profile_config'] = [line for line in config.splitlines()
                                       if any(s in line for s in ('PERF_EVENTS', 'HW_PERF_EVENTS',
                                                                  'PROFILING', 'ROCKCHIP_DFI',
                                                                  'ROCKCHIP_DMC', 'FTRACE', 'ARM_PMU'))]
except OSError as error:
    result['kernel_profile_config'] = dict(error=str(error))
print(json.dumps(result, indent=2))
