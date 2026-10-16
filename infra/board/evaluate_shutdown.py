"""Accept a completed local A/B archive using the locked host evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
parser.add_argument('--edges',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--wait',type=float,default=0,help='Local-file completion wait, seconds; no SSH/model polling')
args=parser.parse_args();repo=Path(__file__).resolve().parents[2]
end=time.monotonic()+args.wait
while not (args.directory/'ab_summary.json').exists() or not (args.directory/'result.json').exists():
    result=args.directory/'result.json'
    if result.exists() and json.loads(result.read_text())['exit_code']!=0:
        raise RuntimeError('A/B failed; inspect '+str(args.directory))
    if time.monotonic()>=end:raise TimeoutError('A/B archive incomplete: '+str(args.directory))
    time.sleep(1)
summary=json.loads((args.directory/'ab_summary.json').read_text());assert summary['status']=='pass'
assert json.loads((args.directory/'result.json').read_text())['exit_code']==0
edges=json.loads(args.edges.read_text());assert len(edges)==3 and all(all(v==0 for v in case['process_exits'].values()) for case in edges)
assert any(case['imu_wait_observed'] for case in edges)
python=repo/'infra/desktop/.venv/bin/python'
evaluator=repo/'infra/desktop/scripts/evaluate_baseline.py'
evaluations={}
for name in ['baseline','candidate']:
    with (args.directory/(name+'-evaluation.log')).open('w') as stream:
        subprocess.run([str(python),str(evaluator),str(args.directory/name)],stdout=stream,stderr=subprocess.STDOUT,check=True)
    evaluations[name]=json.loads((args.directory/name/'evaluation.json').read_text())
a,b=evaluations['baseline'],evaluations['candidate']
limits=dict(ate_rmse_m=a['ate_translation_m']['rmse']*1.05+.001,rpe_rmse_m=a['rpe_translation_m_one_pose_step']['rmse']*1.05+.00001)
assert a['matched_poses']==b['matched_poses']==1819
assert b['ate_translation_m']['rmse']<=limits['ate_rmse_m'],(b['ate_translation_m'],limits)
assert b['rpe_translation_m_one_pose_step']['rmse']<=limits['rpe_rmse_m'],(b['rpe_translation_m_one_pose_step'],limits)
sys.path.insert(0,str(repo/'infra/board'))
from common import yaml_file
parameters=[]
for name in ['baseline','candidate']:
    config=args.directory/name/'config/vio.yaml'
    data=yaml_file(config,Path('/nonexistent-vins-install'))
    for field in ['output_path','pose_graph_save_path']:data.pop(field)
    parameters.append(data)
assert parameters[0]==parameters[1],'Algorithm/calibration selection parameters differ'
for camera in ['cam0.yaml','cam1.yaml']:
    assert (args.directory/'baseline/config'/camera).read_bytes()==(args.directory/'candidate/config'/camera).read_bytes()
record=dict(status='pass',accuracy_accepted=True,edge_tests_passed=True,candidate_binary_sha256=summary['candidate_binary_sha256'],candidate_library_sha256=summary['candidate_library_sha256'],ab_summary_sha256=hashlib.sha256((args.directory/'ab_summary.json').read_bytes()).hexdigest(),edge_summary_sha256=hashlib.sha256(args.edges.read_bytes()).hexdigest(),algorithm_and_calibration_equal=True,limits=limits,accuracy={name:dict(poses=value['estimated_poses'],matched=value['matched_poses'],ate_rmse_m=value['ate_translation_m']['rmse'],rpe_rmse_m=value['rpe_translation_m_one_pose_step']['rmse']) for name,value in evaluations.items()},exit_codes={name:case['run']['process_exits'] for name,case in summary['cases'].items()},resources_note='See ab_summary.json; CPU last samples are lower bounds; sampled RSS/PSS by process; DDR/power unavailable; no performance gain claim')
with args.output.open('x') as stream:stream.write(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
