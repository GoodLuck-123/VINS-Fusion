"""Check relocated package integrity, ELF closure and intentional corruption."""
import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,digest
r=json.loads((ROOT/'releases/host.json').read_text());source=Path(r['install']);dest=ROOT/'build/package-validation/relocated install';dest.parent.mkdir(exist_ok=True)
if dest.exists():shutil.rmtree(dest)
shutil.copytree(source,dest,copy_function=os.link)
# Run with a genuinely empty shell environment; paths contain spaces deliberately.
env={'HOME':os.environ['HOME'],'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
def check():return subprocess.run([dest/'bin/vins','check'],env=env,capture_output=True,text=True)
report={};result=check();assert result.returncode==0,result.stderr;report['relocated_clean_check']={'exit':result.returncode,'release':json.loads(result.stdout)}
changed=dest/'bin/vins_observer';original=changed.read_bytes();changed.unlink();changed.write_bytes(original+b'corruption');changed.chmod(0o755)
result=check();assert result.returncode and 'corrupt' in result.stderr,result;report['corrupt_file']={'exit':result.returncode,'error':result.stderr.strip()}
changed.unlink();os.link(source/'bin/vins_observer',changed)
missing=dest/'lib/libvins_lib.so';missing.unlink();result=check();assert result.returncode and 'missing/corrupt' in result.stderr;report['missing_library']={'exit':result.returncode,'error':result.stderr.strip()}
os.link(source/'lib/libvins_lib.so',missing)
elfs=0
for p in dest.rglob('*'):
 if not p.is_file():continue
 with p.open('rb') as f:
  if f.read(4)!=b'\x7fELF':continue
 elfs+=1;dynamic=subprocess.check_output(['readelf','-d',p],text=True,stderr=subprocess.DEVNULL)
 assert '(RPATH)' not in dynamic and '(RUNPATH)' not in dynamic,str(p)
report['elfs_without_build_rpath']=elfs
atomic(ROOT/'evidence/v0.1/package-checks.json',report);print('PACKAGE CHECKS PASSED',elfs)
