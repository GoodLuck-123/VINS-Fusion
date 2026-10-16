"""Execute the real CLI on generated bags, keeping negative evidence."""
from pathlib import Path
import json
import subprocess
import sys
root,fixtures,logs=map(Path,sys.argv[1:]);summary=[]
for name,full,expected in [('valid',False,0),('valid',True,0),('missing-imu',False,1),('wrong-type',False,1),('no-overlap',False,1),('duplicate',False,0),('duplicate',True,1),('backwards',True,1)]:
    result=subprocess.run([str(root/'bin/check'),'--bag',str(fixtures/(name+'.bag')),'--json','-',*(['--timestamps'] if full else [])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    key=name+('-full' if full else '-fast');(logs/(key+'.json')).write_text(result.stdout)
    assert result.returncode==expected,(key,result.returncode,result.stdout,result.stderr)
    json.loads(result.stdout)
    summary.append(dict(case=key,exit_code=result.returncode))
for options in [['--arc','--dir','--min-free-mb','1e20'],['--mode','sensor'],['--timestamps']]:
    result=subprocess.run([str(root/'bin/check'),*options],capture_output=True,text=True)
    assert result.returncode in (1,2),(options,result.stdout,result.stderr)
    summary.append(dict(options=options,exit_code=result.returncode))
(logs/'fixture_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
