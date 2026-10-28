"""Read-only version gates plus a small report; no hardware mutation or new task."""
import json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import load,digest,atomic
from cli import control,rpc
E=ROOT/'evidence/hardware-v02'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
frozen=json.loads((ROOT/'evidence/intake/20261028/frozen-refs.json').read_text())['frozen_refs']
for row in frozen:assert git('rev-parse',row['ref'])==row['object'],row
assert git('branch','--show-current')=='codex/vins-platform'
assert not git('diff','vins-platform-v0.1.0','--','vins_estimator','camera_models','runtime/observer','buildkit/sources.lock.json')
packages={}
for target in ['host','board']:
    p=json.loads((ROOT/'releases'/(target+'.json')).read_text());install=Path(p['install']);meta=json.loads((install/'release.json').read_text())
    assert meta['version']=='0.2.0';assert digest(p['archive'])==p['sha256']
    files=json.loads((install/'files.json').read_text())
    for name,want in files.items():assert digest(install/name)==want,name
    p['manifest_verified_files']=len(files);p['runtime_source_commit']=meta['platform_commit'];packages[target]=p
atomic(E/'packages.json',packages)
atomic(E/'final-audit.json',dict(status='pending'))
maps=json.loads((E/'runtime-maps-private.json').read_text());assert maps['unexpected_external_libraries']==[]
assert maps['install'].endswith('/'+packages['board']['id']+'/install')
for target in ['host','board']:
    replay=json.loads((E/('motion-replay-'+target+'.json')).read_text())
    assert replay['phase']=='completed' and replay['initialization_log_count']==1 and replay['trajectory_poses']>0
    assert abs(replay['tail_s'])<=.1 and all(x==0 for x in replay['process_exits'].values())
links=[]
for p in [ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').glob('*.md')),*sorted(ROOT.glob('*/README.md'))]:
    for link in re.findall(r'\]\(([^\s)]+)(?:\s+[^)]*)?\)',p.read_text()):
        if re.match(r'^[a-z]+:|^#',link):continue
        if not (p.parent/link.split('#')[0]).exists():links.append((str(p.relative_to(ROOT)),link))
assert not links,links
tracked=git('ls-files').splitlines()
for name in tracked:
    if name.split('/')[0] in ['releases','cache','build','data','experiments']:assert name.endswith('/README.md'),name
    assert not name.endswith(('.bag','.deb','.so','.tar.gz')),name
    if name.startswith('third_party/'):assert name.startswith('third_party/drivers/') or name in ['third_party/README.md','third_party/.gitignore'],name
code='''import json,sys
from pathlib import Path
s=json.loads(sys.argv[1]);groups=set(s.get('child_pids',{}).values());alive=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  fields=(p/'stat').read_text().split(') ',1)[1].split()
  if fields[0]!='Z' and int(fields[2]) in groups and s['install'].encode() in (p/'cmdline').read_bytes():alive.append(int(p.name))
 except (OSError,IndexError,ValueError):pass
print(json.dumps(alive))
'''
cleanup={}
for target in ['host','board']:
    c=load(ROOT/'project.example.yaml');c['_host']=target=='host';s=control(c,'status');assert s['phase']=='completed' and s['exit_code']==0,s
    alive=rpc(c,code,[json.dumps(s)]);assert not alive,alive;cleanup[target]=dict(task=s['task'],phase=s['phase'],live_owned_processes=alive)
atomic(E/'packages.json',packages)
atomic(E/'final-audit.json',dict(status='pass',frozen_refs_unchanged=len(frozen),core_and_observer_unchanged_since_v01=True,markdown_links='pass',no_generated_data_tracked=True,package_manifests_and_archives='pass',private_sdk_maps='pass',cleanup=cleanup))
print('V0.2 FINAL AUDIT PASSED')
