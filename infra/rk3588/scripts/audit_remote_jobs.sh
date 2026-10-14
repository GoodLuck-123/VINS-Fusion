#!/usr/bin/env bash
set -euo pipefail
/usr/bin/python3 - <<'PY' > "$VINS_REMOTE_ROOT/logs/remote_jobs.json"
import json, os, pathlib, time
root = pathlib.Path.home() / 'vins-workspace/jobs'
current = pathlib.Path(os.environ['VINS_REMOTE_ROOT']).resolve()
jobs = []
for job in sorted(root.iterdir()):
    if not job.is_dir() or job.resolve() == current:
        continue
    logs = job / 'logs'
    def read(name):
        path = logs / name
        return path.read_text().strip() if path.is_file() else None
    jobs.append(dict(job=job.name, exit_code=read('exit_code'),
                     start_utc=read('start_utc'), end_utc=read('end_utc')))
active = []
for directory in pathlib.Path('/proc').iterdir():
    if not directory.name.isdigit() or int(directory.name) == os.getpid():
        continue
    try:
        argv = (directory / 'cmdline').read_bytes().decode(errors='replace').split('\0')
    except OSError:
        continue
    if any(str(root) + '/' in value for value in argv) and not any(str(current) in value for value in argv):
        active.append(dict(pid=int(directory.name), argv=argv))
print(json.dumps(dict(board_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                     prior_jobs=jobs, active_prior_task_processes=active), indent=2))
PY
