"""Replay the actual user-motion capture through each private target runtime."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import load,atomic
from cli import run,control
c=load(ROOT/'project.example.yaml');c['_host']=sys.argv[1]=='host';target='host' if c['_host'] else 'board'
c['run'].update(mode='replay',name='field-motion-replay-v02',drain_timeout_s=90)
c['dataset'].update(bag=str(ROOT/'experiments/field-motion-v02/board/001/raw'),duration_s=None,start_s=0,ground_truth=None)
c['results']['raw_data']='on_request'
assert run(c)==0
state=control(c,'status');assert state['phase']=='completed' and state['initialization_log_count']>0 and not state.get('forced_cleanup'),state
atomic(ROOT/'evidence/hardware-v02'/('motion-replay-'+target+'.json'),state)
print('ACTUAL MOTION SPLIT-BAG REPLAY PASSED',target)
