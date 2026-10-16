"""Per-job SSH helper: durable execution, live logs and explicit cancellation.

Uploaded by the C++ client; no daemon, ROS dependency or third-party Python package.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def emit(job, code, message='', **fields):
    if not re.fullmatch('[A-Z][A-Z0-9_]*', code):
        raise ValueError('Invalid event code: ' + code)
    event = dict(job=job.name, code=code, message=message,
                 utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 monotonic_ns=time.monotonic_ns(), pid=os.getpid(), **fields)
    fd = os.open(str(job / 'logs/events.jsonl'), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (json.dumps(event, ensure_ascii=False) + '\n').encode())
    finally:
        os.close(fd)


def ticks(pid):
    try:
        return Path('/proc/{}/stat'.format(pid)).read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def atomic(path, content):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(content)
    temporary.replace(path)


def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def worker(job, timeout, payload, workspace, cwd, env_file):
    # A shell background job may inherit SIGINT=ignored. Restore it before
    # launching scripts so their Python finally/ROS shutdown handlers can run.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    logs = job / 'logs'
    atomic(logs / 'worker.json', json.dumps(dict(pid=os.getpid(), ticks=ticks(os.getpid()))) + '\n')
    cancelled = []
    signal.signal(signal.SIGUSR1, lambda *_: cancelled.append(True))
    emit(job, 'JOB_STARTED', 'Remote script started', timeout_s=timeout)
    environment = dict(os.environ, VINS_REMOTE_ROOT=str(job), VINS_REMOTE_PAYLOAD=str(job / payload),
                       VINS_REMOTE_WORKSPACE=workspace, VINS_REMOTE_CWD=cwd, VINS_REMOTE_ENV=env_file,
                       PYTHONUNBUFFERED='1')
    # Export the stage-reporting function without initializing a ROS environment
    # in generic/legacy jobs. Their scripts select their own interpreter/environment.
    bootstrap = '''vins_event() { /usr/bin/python3 "$VINS_REMOTE_ROOT/remote_agent.py" emit "$VINS_REMOTE_ROOT" "$@"; }
export -f vins_event
exec bash "$1"
'''
    code, reason = 125, 'failed'
    process = None
    start = time.monotonic()
    heartbeat = start
    stopping = None
    try:
        with (logs / 'console.log').open('wb', buffering=0) as console:
            process = subprocess.Popen(['bash', '-c', bootstrap, '_', str(job / 'run-script.sh')],
                                       cwd=str(job), env=environment, stdout=console,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            emit(job, 'PROCESS_STARTED', 'Script process group', child_pid=process.pid)
            while process.poll() is None:
                now = time.monotonic()
                if stopping is None and (cancelled or now - start >= timeout):
                    reason = 'cancelled' if cancelled else 'timeout'
                    emit(job, 'CANCEL_REQUESTED' if cancelled else 'TIMEOUT', reason)
                    signal_group(process.pid, signal.SIGINT)
                    stopping = now
                elif stopping is not None:
                    elapsed = now - stopping
                    if elapsed >= 15:
                        signal_group(process.pid, signal.SIGKILL)
                    elif elapsed >= 10:
                        signal_group(process.pid, signal.SIGTERM)
                if now - heartbeat >= 5:
                    emit(job, 'RUNNING', 'Process is alive; this is not a health verdict',
                         elapsed_s=round(now - start, 1), child_pid=process.pid)
                    heartbeat = now
                time.sleep(0.1)
            raw_code = process.returncode
            code = 130 if reason == 'cancelled' else 124 if reason == 'timeout' else (
                raw_code if raw_code >= 0 else 128 - raw_code)
            if reason not in ('cancelled', 'timeout'):
                reason = 'complete' if code == 0 else 'failed'
            emit(job, 'JOB_FINISHED', reason, exit_code=code, script_exit_code=raw_code)
    except BaseException as error:
        emit(job, 'AGENT_ERROR', str(error))
        if process and process.poll() is None:
            signal_group(process.pid, signal.SIGKILL)
            process.wait()
    finally:
        # Remove descendants still in the owned script process group. Programs
        # that create their own sessions must implement their own cleanup.
        if process:
            signal_group(process.pid, signal.SIGTERM)
        atomic(logs / 'result.json', json.dumps(dict(status=reason, exit_code=code,
                                                   elapsed_s=time.monotonic() - start)) + '\n')
        atomic(logs / 'exit_code', str(code) + '\n')


def follow(job, events_only=False):
    logs = job / 'logs'
    offsets = {}
    last_activity = time.monotonic()
    try:
        while True:
            finished = (logs / 'exit_code').is_file()
            paths = [logs / 'events.jsonl']
            if not events_only:
                paths += sorted(p for p in logs.rglob('*.log') if p.name != 'launcher.log')
            for path in paths:
                if not path.is_file():
                    continue
                offset, pending = offsets.get(str(path), (0, b''))
                with path.open('rb') as stream:
                    if path.stat().st_size < offset:
                        offset, pending = 0, b''
                    stream.seek(offset)
                    chunk = stream.read(65536)
                    offset = stream.tell()
                if chunk:
                    last_activity = time.monotonic()
                data = pending + chunk
                lines = data.split(b'\n')
                pending = lines.pop()
                if finished and pending:
                    lines.append(pending)
                    pending = b''
                for line in lines:
                    text = line.decode('utf-8', errors='replace')
                    if path.name == 'events.jsonl':
                        if events_only:
                            print(text, flush=True)
                        else:
                            event = json.loads(text)
                            print('[{}] {}{}'.format(event['code'], event['message'],
                                  ' exit=' + str(event['exit_code']) if 'exit_code' in event else ''), flush=True)
                    else:
                        print('[{}] {}'.format(path.relative_to(logs), text), flush=True)
                offsets[str(path)] = offset, pending
            if finished:
                # Drain files larger than one read before returning their exit.
                if any(p.is_file() and p.stat().st_size > offsets.get(str(p), (0, b''))[0] for p in paths):
                    continue
                return int((logs / 'exit_code').read_text())
            info_path = logs / 'worker.json'
            if info_path.is_file():
                info = json.loads(info_path.read_text())
                if ticks(info['pid']) != info['ticks']:
                    print('[JOB_STATE_UNKNOWN] Worker disappeared without a result; retain logs', file=sys.stderr)
                    return 125
            elif time.monotonic() - last_activity > 30:
                print('[JOB_STATE_UNKNOWN] Worker did not publish its identity', file=sys.stderr)
                return 125
            time.sleep(0.2)
    except (KeyboardInterrupt, BrokenPipeError):
        return 130


def stop(job):
    if (job / 'logs/exit_code').exists():
        return
    path = job / 'logs/worker.json'
    deadline = time.monotonic() + 5
    while not path.exists() and not (job / 'logs/exit_code').exists():
        if time.monotonic() > deadline:
            raise RuntimeError('Worker did not initialize; stop cannot verify ownership')
        time.sleep(0.1)
    if (job / 'logs/exit_code').exists():
        return
    info = json.loads(path.read_text())
    if ticks(info['pid']) != info['ticks']:
        raise RuntimeError('Worker identity changed; refusing to signal a reused PID')
    os.kill(info['pid'], signal.SIGUSR1)


def main():
    mode, raw_job = sys.argv[1:3]
    job = Path(raw_job).resolve()
    if mode == 'worker':
        worker(job, int(sys.argv[3]), *sys.argv[4:8])
    elif mode == 'follow':
        raise SystemExit(follow(job, '--events-only' in sys.argv[3:]))
    elif mode == 'stop':
        stop(job)
    elif mode == 'emit':
        emit(job, sys.argv[3], ' '.join(sys.argv[4:]))
    else:
        raise ValueError('Unknown agent mode')


if __name__ == '__main__':
    main()
