"""Regression: unused topics outlive the required image/IMU streams."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,load
c=load(ROOT/'project.yaml');path=ROOT/'cache/endpoint-test.json';atomic(path,c)
# Invoked after sourcing a private host package.
r=subprocess.run([sys.executable,ROOT/'runtime/bag_info.py',path],capture_output=True,text=True,check=True);report=json.loads(r.stdout)
assert report['topics']['/cam0/image_raw']['bag_records_full_file']==3682
assert report['topics']['/imu0']['bag_records_full_file']==36820
assert report['duration_s']>184 and report['duration_s']<185
atomic(ROOT/'evidence/v0.1/bag-endpoints.json',report);print('SELECTED TOPIC ENDPOINTS PASSED')
