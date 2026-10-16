"""Exercise remote CLI on the real board without replaying VIO data.

Requires an already accepted ROS 1 release. Creates isolated jobs/incoming files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pty
import queue
import select
import shlex
import signal
import subprocess
import threading
import time


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tool',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--release',default='/home/firefly/vins-workspace/releases/ros1-v0.1/install')
    ap.add_argument('--manifest-sha',required=True)
    ap.add_argument('--run-script',type=Path,required=True)
    args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    tool=str(args.tool.resolve());checks={};counter=0

    def call(name,*items,expected=0):
        print('[CHECK]',name,flush=True)
        command=[tool,*map(str,items)]
        with (out/(name+'.log')).open('w') as log:
            p=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        if p.returncode!=expected:
            raise RuntimeError(name+' exit '+str(p.returncode)+': '+(out/(name+'.log')).read_text()[-3000:])
        checks[name]=dict(exit_code=p.returncode)
        return (out/(name+'.log')).read_text()

    cfg=json.loads(subprocess.check_output([tool,'--print-config'],text=True))
    root=cfg['root'];remote_root='"$HOME"/'+shlex.quote(root) if not root.startswith('/') else shlex.quote(root)
    activate='''set -eu
+workspace=ROOT
+release=RELEASE
+cd "$release"
+printf '%s  SHA256SUMS\n' EXPECTED | sha256sum -c -
+sha256sum --quiet -c SHA256SUMS
+mkdir -p "$workspace/projects/vins"
+if test -L "$workspace/install"; then
+  test "$(readlink -f "$workspace/install")" = "$(readlink -f "$release")"
+else
+  test ! -e "$workspace/install"
+  ln -s "$release" "$workspace/install"
+fi
+printf 'DEFAULT_INSTALL_VERIFIED %s\n' "$workspace/install"
+'''.replace('\n+','\n').replace('ROOT',remote_root).replace('RELEASE',shlex.quote(args.release)).replace('EXPECTED',shlex.quote(args.manifest_sha))
    call('bootstrap','--exec','--no-env','--','bash','-c',activate)
    text=call('environment','--exec','--','bash','-c','printf "INSTALL=%s\\nCWD=%s\\n" "$VINS_INSTALL_ROOT" "$PWD"; command -v roscore; python3 --version')
    assert '/projects/vins' in text and '/install/runtime/ros/bin/roscore' in text and 'Python 3.8' in text

    # No arbitrary shell interpretation of the uploaded directory name.
    payload=out/("probe ' "+str(time.time_ns()));payload.mkdir()
    (payload/'binary.dat').write_bytes(os.urandom(1024*1024))
    call('send',str(payload)+'/','--send')
    call('receive','incoming/'+payload.name+'/','--receive','--dest',out/'received')
    assert hashlib.sha256((out/'received'/payload.name/'binary.dat').read_bytes()).digest()==hashlib.sha256((payload/'binary.dat').read_bytes()).digest()
    checks['transfer_sha256']=True

    def script(body):
        nonlocal counter
        counter+=1;p=out/('probe-'+str(counter)+'.sh');p.write_text('set -eu\n'+body);return p

    def run(name,body,*options,expected=0):
        logs=out/(name+'-board')
        call(name,payload,'--run',script(body),'--output',logs,*options,expected=expected)
        return logs,json.loads((logs/'remote_job.json').read_text())['job']

    logs=out/'live-board';live_script=script('vins_event PROBE_READY ready\nmkdir -p logs/nested\necho first > logs/nested/vins.log\nsleep 3\necho last >> logs/nested/vins.log\n')
    with (out/'live.log').open('w') as log:
        p=subprocess.Popen([tool,str(payload),'--run',str(live_script),'--output',str(logs)],stdout=subprocess.PIPE,stderr=log,text=True)
        arrivals=queue.Queue();seen=[]
        def reader():
            for line in p.stdout:
                log.write(line);log.flush();seen.append(line);arrivals.put(line)
        thread=threading.Thread(target=reader);thread.start()
        deadline=time.monotonic()+30
        while True:
            line=arrivals.get(timeout=max(.1,deadline-time.monotonic()))
            if '[nested/vins.log] first' in line:break
        assert p.poll() is None,'Output only arrived after completion'
        assert p.wait(timeout=30)==0
        thread.join(timeout=5);p.stdout.close()
    assert (logs/'nested/vins.log').read_text()=='first\nlast\n'
    checks['live_before_completion']=True
    print('[CHECK] live_before_completion passed',flush=True)
    run('failure','echo deliberate-failure\nexit 7\n',expected=7)
    run('timeout',"trap 'echo cleanup > logs/cleanup; exit 0' INT TERM\nwhile :; do sleep 1; done\n",'--timeout','1',expected=124)

    detached,job=run('detached','echo unique >> logs/started\nsleep 4\n','--detach')
    call('reconnect',job,'--follow','--output',detached)
    assert (detached/'started').read_text()=='unique\n'
    call('recollect',job,'--collect',detached)

    stopped,job=run('stop-start',"trap 'echo cleanup > logs/cleanup; exit 0' INT TERM\nvins_event STOP_READY ready\nwhile :; do sleep 1; done\n",'--detach')
    call('stop',job,'--stop','--output',stopped,expected=130)
    assert json.loads((stopped/'result.json').read_text())['status']=='cancelled'

    # Actual interactive SSH PTY, not a mock: initialize then return to the host.
    print('[CHECK] interactive SSH',flush=True)
    pid,fd=pty.fork()
    if pid==0:
        os.execv(tool,[tool,'--remote'])
    transcript=b'';sent=False;deadline=time.monotonic()+30
    try:
        while time.monotonic()<deadline:
            ready,_,_=select.select([fd],[],[],.2)
            if ready:
                try:data=os.read(fd,65536)
                except OSError:break
                if not data:break
                transcript+=data
                if not sent and b'[REMOTE_READY]' in transcript:
                    os.write(fd,b'printf "__REMOTE_OK__%s\\n" "$VINS_INSTALL_ROOT"; pwd; command -v roscore; exit\n');sent=True
            done,status=os.waitpid(pid,os.WNOHANG)
            if done:
                assert os.waitstatus_to_exitcode(status)==0
                pid=0;break
        else:raise TimeoutError('Interactive shell timed out')
    finally:
        os.close(fd)
        if pid:
            done,status=os.waitpid(pid,os.WNOHANG)
            if not done:os.kill(pid,signal.SIGTERM);os.waitpid(pid,0)
    (out/'interactive.log').write_bytes(transcript)
    assert sent and b'/projects/vins' in transcript and b'/install/runtime/ros/bin/roscore' in transcript
    checks['interactive_pty']=True

    print('[CHECK] run.py default install and log recovery',flush=True)
    with (out/'run-default.log').open('w') as log:
        code=subprocess.run(['/usr/bin/python3',str(args.run_script),'--tool',tool,'--output',str(out/'run-default-board')],stdout=log,stderr=subprocess.STDOUT,timeout=240).returncode
    assert code==0,(out/'run-default.log').read_text()[-3000:]
    validation=json.loads((out/'run-default-board/runtime-check/logs/validation.json').read_text())
    assert validation['subscriptions_ready'] and validation['roscore_exit_code']==0
    checks['runtime_default']=dict(verified_files=validation['verified_files'],vins_exit_code=validation['vins_exit_code'],roscore_exit_code=validation['roscore_exit_code'])
    call('no-vins-residual','--exec','--no-env','--','bash','-c','if pgrep -a -x vins_node; then exit 1; fi')
    summary=dict(status='passed',checks=checks,settings=cfg,no_vio_replay=True,root=str(out))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
