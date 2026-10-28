from pathlib import Path
import subprocess,json,re,hashlib,argparse
import yaml
parser=argparse.ArgumentParser(description='Read-only design/source checks; optional local return archive')
parser.add_argument('--write-report',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[4]
ev=root/'evidence/intake/20261028'
def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
config=yaml.safe_load((root/'project.example.yaml').read_text())
assert config['schema_version']==1 and config['run']['mode']=='replay'
assert config['inputs']['imu']['enabled'] is True
class Loader(yaml.SafeLoader):pass
Loader.add_constructor('tag:yaml.org,2002:opencv-matrix',lambda l,n:l.construct_mapping(n,deep=True))
def original(name):
 s=git('show','be55a93:'+name)
 return yaml.load('\n'.join(x for x in s.splitlines() if not x.startswith('%YAML')),Loader=Loader)
mono=original('config/euroc/euroc_mono_imu_config.yaml'); cal=original('config/euroc/cam0_mei.yaml')
for key,value in config['vins'].items():
 expected=mono[key]
 if key=='body_T_cam0':expected=[expected['data'][i:i+4] for i in range(0,16,4)]
 assert value==expected, (key,value,expected)
camera=config['inputs']['camera']
for key,other in [('width','image_width'),('height','image_height'),('topic','image0_topic')]:assert camera[key]==mono[other]
assert config['inputs']['imu']['topic']==mono['imu_topic']
cc=camera['calibration'];assert cc['model']==cal['model_type']
assert cc['xi']==cal['mirror_parameters']['xi']
assert cc['distortion']==cal['distortion_parameters']
assert cc['projection']==cal['projection_parameters']
source=git('show','be55a93:vins_estimator/src/estimator/parameters.cpp')
readkeys=set(re.findall(r'fsSettings\["([^"]+)"\]',source))
provided=set(config['vins'])|{'image0_topic','image1_topic','imu','imu_topic','output_path','num_of_cam','cam0_calib','cam1_calib','body_T_cam1','image_width','image_height'}
assert not readkeys-provided, readkeys-provided
badlinks=[]
for p in [root/'README.md',root/'AGENTS.md',*sorted((root/'docs').glob('*.md')),*sorted(root.glob('*/README.md')),ev/'README.md']:
 for target in re.findall(r'\]\(([^\s)]+)(?:\s+[^)]*)?\)',p.read_text()):
  if re.match(r'^[a-z]+:|^#',target):continue
  candidate=p.parent/target.split('#')[0]
  if not candidate.exists():badlinks.append((str(p.relative_to(root)),target))
assert not badlinks,badlinks
frozen=json.loads((ev/'frozen-refs.json').read_text())
for row in frozen['frozen_refs']:assert git('rev-parse',row['ref'])==row['object'],row['ref']
assert git('branch','--show-current')=='codex/vins-platform'
for row in json.loads((ev/'removed-configs.json').read_text())['files']:
 original_bytes=subprocess.check_output(['git','-C',str(root),'show','be55a93:'+row['path']])
 assert hashlib.sha256(original_bytes).hexdigest()==row['sha256']
 assert not (root/row['path']).exists()
core=git('diff','be55a93','--','*.cpp','*.cc','*.h','*.hpp','*CMakeLists.txt','LICENCE')
assert not core,'Algorithm/build source changed'
assert (root/'docs/90_UPSTREAM_README.md').read_bytes()==subprocess.check_output(['git','-C',str(root),'show','be55a93:README.md'])
return_manifest=root/'experiments/platform-intake/001/board-return-sha256.txt'
rows=return_manifest.read_text().splitlines() if return_manifest.exists() else []
checked=0 if rows else None
for row in rows:
 digest,name=row.split(maxsplit=1)
 if name.startswith('/tmp/vins-intake-sdk-ShpHTm/'):
  local=root/'experiments/platform-intake/001/camera-sdk'/Path(name).relative_to('/tmp/vins-intake-sdk-ShpHTm')
 elif name.startswith('/tmp/vins-platform-intake-imu/'):
  local=root/'experiments/platform-intake/001/imu-ros'/Path(name).relative_to('/tmp/vins-platform-intake-imu')
 else:raise AssertionError(name)
 assert hashlib.sha256(local.read_bytes()).hexdigest()==digest,name
 checked+=1
report={'schema_and_vins_mapping':'pass','all_native_vins_keys_accounted_for':len(readkeys),'euroc_parameters':'exact parsed equality including calibration','local_markdown_links':'pass','frozen_refs_unchanged':len(frozen['frozen_refs']),'removed_configs_recoverable':len(json.loads((ev/'removed-configs.json').read_text())['files']),'cpp_cmake_license_unchanged':True,'original_readme_preserved_exactly':True,'returned_board_files_sha256_match':checked,'new_cli_implemented':False,'new_release_built':False}
if args.write_report:(ev/'design-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
