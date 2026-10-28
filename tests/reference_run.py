"""Run the pristine reference through the same user CLI; restore selected package."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import atomic
from cli import package_fingerprint
import yaml

target=sys.argv[1];record=ROOT/'releases'/(target+'.json');saved=record.read_bytes();reference=json.loads((ROOT/'build'/(target+'-reference-package.json')).read_text());reference['input_fingerprint']=package_fingerprint()
config=yaml.safe_load((ROOT/'project.yaml').read_text());config['run']['name']='euroc-reference';config_path=ROOT/'reference-validation.yaml';config_path.write_text(yaml.safe_dump(config,sort_keys=False))
try:
    atomic(record,reference)
    result=subprocess.run([ROOT/'vins','-c',config_path,'run',*(['--host'] if target=='host' else [])])
    # Nonzero shutdown is the expected pristine-reference observation, never hide it.
    print('REFERENCE CLI EXIT',result.returncode,flush=True)
finally:
    record.write_bytes(saved)
