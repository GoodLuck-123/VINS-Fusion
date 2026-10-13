"""Run a local phase, preserve its terminal event, and invoke an optional local hook once."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--completion-hook', type=Path)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
if not command:
    parser.error('A command is required')
directory = args.directory.resolve()
directory.mkdir(parents=True, exist_ok=False)
hook = json.loads(args.completion_hook.read_text()) if args.completion_hook else []
if not isinstance(hook, list) or not all(isinstance(arg, str) for arg in hook):
    raise ValueError('Completion hook must contain a JSON argv array')
event = dict(command=command, pid=os.getpid(), status='running',
             start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
(directory / 'state.json').write_text(json.dumps(event, indent=2) + '\n')
try:
    with (directory / 'console.log').open('x') as log:
        env = os.environ.copy()
        env['VINS_PHASE_DIRECTORY'] = str(directory)
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    event.update(status='complete' if result.returncode == 0 else 'failed', exit_code=result.returncode)
except BaseException as error:
    event.update(status='failed', reason=str(error))
event['end_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
event_path = directory / 'event.json'
event_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + '\n')
(directory / 'state.json').write_text(json.dumps(event, ensure_ascii=False, indent=2) + '\n')
if hook:
    with (directory / 'hook.log').open('x') as log:
        try:
            notification = subprocess.run([*hook, str(event_path)], stdout=log, stderr=subprocess.STDOUT, timeout=30)
            event['notification_exit_code'] = notification.returncode
        except Exception as error:
            event['notification_error'] = str(error)
    (directory / 'state.json').write_text(json.dumps(event, ensure_ascii=False, indent=2) + '\n')
raise SystemExit(0 if event['status'] == 'complete' else 1)
