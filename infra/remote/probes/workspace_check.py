"""Validate production workspace defaults against an idle board; no VIO input."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--name',default='workspace-layout-check01',help='Unused readable board run name')
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    tool=str(args.tool.resolve())
    cfg=json.loads(subprocess.check_output([tool,'--print-config'],text=True))
    def call(name,*argv,expected=0):
        p=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=240)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        assert p.returncode==expected,(name,p.returncode,p.stdout[-2000:],p.stderr[-2000:])
        return p.stdout
    # All paths are derived from the same configured root/cwd; no old jobs move.
    setup='''import json,os
from pathlib import Path
cfg=json.loads(CONFIG)
def expand(s):
 p=Path(s).expanduser()
 return p if p.is_absolute() else Path.home()/p
root=expand(cfg['root']);cwd=expand(cfg['cwd'])
active=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  argv=(proc/'cmdline').read_bytes().split(b'\\0')
  if any(Path(a.decode(errors='replace')).name in ('vins_node','roscore','rosmaster') for a in argv[:2]):active.append(proc.name)
 except (OSError,ValueError):pass
assert not active,('Existing ROS/VINS processes; refusing overlap',active)
install=(root/'install').resolve(strict=True)
assert install==root/'releases/ros1-v0.1/install',str(install)
manifest=install/'SHA256SUMS'
import hashlib
assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='6e45dd5a9c17156a39f3983f3d7cac7d633488d9bd29be229e936f1ed909e836'
for name in ('data/euroc','config','runs'):(cwd/name).mkdir(parents=True,exist_ok=True)
source=root/'datasets/euroc_20261014/MH_01_easy.bag'
assert source.is_file(),str(source)
link=cwd/'data/euroc/MH_01_easy.bag'
if link.exists() or link.is_symlink():assert link.is_symlink() and link.resolve()==source
else:link.symlink_to(source)
print(json.dumps(dict(root=str(root),cwd=str(cwd),install=str(install),bag=str(link),bag_source=str(source),no_live_ros=True)))
'''.replace('CONFIG',repr(json.dumps(cfg)))
    state=json.loads(call('setup',tool,'--exec','--no-env','--','/usr/bin/python3','-c',setup))
    fixture=out/'workspace-layout-note.txt';fixture.write_text('Default upload and experiment working directory are the same.\n')
    call('send',tool,fixture,'--send')
    digest=call('uploaded',tool,'--exec','--','sha256sum',fixture.name).split()[0]
    assert digest==hashlib.sha256(fixture.read_bytes()).hexdigest()
    call('receive',tool,state['cwd']+'/'+fixture.name,'--receive','--dest',out/'received')
    assert (out/'received'/fixture.name).read_bytes()==fixture.read_bytes()
    call('environment',tool,'--exec','--','bash','-c','pwd; command -v roscore; command -v vins')
    run=Path(__file__).resolve().parents[2]/'release/run.py'
    # Use the same code whether the probe lives in source or a test copy.
    if not run.exists():raise RuntimeError('Run this probe from infra/remote/probes/')
    host=out/'install-check01'
    call('runtime-check',sys.executable,run,'--tool',tool,'--output',host,'--name',args.name)
    receipt=json.loads((host/'remote_job.json').read_text())
    assert receipt['job']==state['cwd']+'/runs/'+args.name,receipt
    check=json.loads((host/'runtime-check/logs/validation.json').read_text())
    assert check['subscriptions_ready'] and check['verified_files']==4217 and check['vins_exit_code']==-6 and check['roscore_exit_code']==0,check
    call('duplicate-refused',sys.executable,run,'--tool',tool,'--name',args.name,'--output',out/'refused-check',expected=2)
    call('collect',tool,receipt['job'],'--collect',out/'recollected')
    assert (out/'recollected/runtime-check/logs/validation.json').read_bytes()==(host/'runtime-check/logs/validation.json').read_bytes()
    end='''import json
from pathlib import Path
root=Path(ROOT);cwd=Path(CWD)
print(json.dumps(dict(install=str((root/'install').resolve()),project={p.name:('symlink' if p.is_symlink() else 'directory' if p.is_dir() else 'file') for p in cwd.iterdir()},runs=sorted(p.name for p in (cwd/'runs').iterdir()))))
'''.replace('ROOT',repr(state['root'])).replace('CWD',repr(state['cwd']))
    final=json.loads(call('layout',tool,'--exec','--no-env','--','/usr/bin/python3','-c',end))
    assert final['install']==state['install']
    result=dict(status='passed',settings=cfg,board=state,layout=final,task=receipt,transfer_sha256=digest,verified_files=check['verified_files'],subscriptions_ready=check['subscriptions_ready'],vins_exit_code=check['vins_exit_code'],roscore_exit_code=check['roscore_exit_code'],no_vio_replay=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
