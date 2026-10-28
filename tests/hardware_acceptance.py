"""Actual board acceptance through existing host APIs; no parallel hardware tasks."""
import copy,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import load,atomic
from cli import run,control,rpc,collect,follow
c=load(ROOT/'field.yaml');c['_host']=False;c['results']['raw_data']='on_request';evidence=ROOT/'evidence/hardware-v02';rows=[]
def capture(name,change=None,maps=False):
    conf=copy.deepcopy(c);conf['run'].update(name=name,duration_s=30 if maps else 4)
    if change:change(conf['inputs']['camera']['device'])
    assert run(conf,True,True)==0
    deadline=time.monotonic()+conf['run']['startup_timeout_s']+15
    while True:
        s=control(conf,'status')
        if s['phase']=='capturing':break
        assert s['phase'] not in ['failed','cancelled','completed'],s
        assert time.monotonic()<deadline,s
        time.sleep(.3)
    if maps:
        report=rpc(conf,(ROOT/'tests/capture_runtime_maps.py').read_text());atomic(evidence/'runtime-maps-private.json',report)
        control(conf,'stop') # Exercise graceful early stop, not timeout/cancellation.
    assert follow(conf,True)==0
    s=control(conf,'status');assert s['phase']=='completed' and not s.get('forced_cleanup'),s
    assert s['recording']['frame_pairing_verified'] and s['recording']['device_frame_ids_contiguous'],s
    atomic(evidence/(name+'.json'),s);rows.append(dict(task=s['task'],recording=s['recording'],process_exits=s['process_exits'],stop_reason=s.get('stop_reason')))
    if maps:
        # on_request first omitted raw; explicitly pulling it must verify a full manifest.
        dest=collect(conf,True);assert json.loads((dest/'transfer.json').read_text())['raw_data_collected']
        atomic(evidence/'private-stop-transfer.json',json.loads((dest/'transfer.json').read_text()))

capture('field-private-stop-v02',maps=True)
capture('field-software-v02',lambda d:d.update(trigger='software',exposure=dict(mode='manual',time_us=8000.,auto_max_us=20000.)))
capture('field-continuous-v02',lambda d:d.update(trigger='continuous'))
capture('field-binning1-v02',lambda d:d.update(binning=1,crop=[768,512,512,512],trigger='software'))
# Restore the default hardware-trigger/binned settings after exercising options.
capture('field-hardware-restored-v02')
atomic(evidence/'hardware-options.json',rows)
print('PRIVATE SDK / HARDWARE OPTIONS / STOP / RAW PULL PASSED')
