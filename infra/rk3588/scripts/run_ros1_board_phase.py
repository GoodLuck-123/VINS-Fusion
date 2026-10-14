"""Upload the original bag once, run one ROS 1 baseline, collect and evaluate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default='firefly@10.106.0.220')
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--runtime-manifest', type=Path,
                        default=REPO / 'infra/rk3588/reference/ros1_runtime_20261014/payload_files.json',
                        help='Host files.json for the accepted deployment; defaults to its frozen archive')
    parser.add_argument('--name', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--data-parent', default='vins-workspace/datasets/euroc_20261014')
    parser.add_argument('--upload-data', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.name):
        parser.error('Use a unique simple result name without path separators')
    bag = WORKSPACE / 'data/euroc/MH_01_easy.bag'
    digest = hashlib.sha256()
    with bag.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    drivers = directory / 'drivers'
    drivers.mkdir()
    plan = dict(runtime=args.runtime, name=args.name, bag=args.data_parent+'/'+bag.name,
                bag_sha256=digest.hexdigest(),
                runtime_manifest_sha256=hashlib.sha256(args.runtime_manifest.read_bytes()).hexdigest(),
                driver_commit=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip())
    (drivers/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    tool = str(WORKSPACE / '.infra/bin/vins-remote')
    if args.upload_data:
        subprocess.run([tool,args.target,str(bag),'--dest',args.data_parent],check=True)
    subprocess.run([tool,args.target,str(drivers),'--run',str(Path(__file__).with_name('ros1_board_phase.sh')),
                    '--output',str(directory/'board'),'--timeout','1800'],check=True)
    env=os.environ.copy()
    for key in ['PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','VIRTUAL_ENV','CONDA_PREFIX']:
        env.pop(key,None)
    env['UV_CACHE_DIR']=str(WORKSPACE/'.infra/uv-cache')
    with (directory/'evaluation.log').open('w') as log:
        subprocess.run(['uv','run','--offline','--project',str(REPO/'infra/desktop'),'--locked','python',
                        str(REPO/'infra/desktop/scripts/evaluate_baseline.py'),str(directory/'board'/args.name),
                        '--label',args.name],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)


if __name__=='__main__':
    main()
