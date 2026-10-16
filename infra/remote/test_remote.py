"""Native C++ integration tests using real rsync and a local SSH transport stand-in."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
import unittest

TOOL = Path(os.environ.get('VINS_REMOTE_TEST_TOOL', str(Path(__file__).resolve().parents[3] / '.infra/bin/vins-remote')))


class RemoteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="remote test ' ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'board home'
        self.home.mkdir()
        self.root = self.home / 'workspace'
        (self.root / 'install').mkdir(parents=True)
        (self.root / 'install/env.sh').write_text('export TEST_REMOTE_ENV=loaded\n')
        fake = self.base / 'fake-bin'
        fake.mkdir()
        ssh = fake / 'ssh'
        ssh.write_text('''#!/usr/bin/python3
import os,subprocess,sys
args=sys.argv[1:]
i=0
while i<len(args) and args[i].startswith('-'):
 if args[i] in ('-o','-l','-p'):i+=2
 else:i+=1
command=' '.join(args[i+1:])
if os.environ.get('FAKE_DISCONNECT') and 'remote_agent.py' in command and ' follow ' in command:sys.exit(255)
try:
 code=subprocess.run(['bash','-c',command],env=dict(os.environ,HOME=os.environ['FAKE_BOARD_HOME'])).returncode
 sys.exit(code if code>=0 else 128-code)
except KeyboardInterrupt:sys.exit(130)
''')
        ssh.chmod(0o755)
        self.env = dict(os.environ, PATH=str(fake)+':'+os.environ['PATH'], FAKE_BOARD_HOME=str(self.home))
        self.payload = self.base / "payload ' $(touch INJECTED)"
        self.payload.write_text('input data\n')

    def args(self,*args):
        return [str(TOOL),'test@board','--root',str(self.root),*map(str,args)]

    def call(self,*args,env=None):
        return subprocess.run(self.args(*args),env=env or self.env,capture_output=True,text=True,timeout=30)

    def script(self,text):
        p=self.base/('script-'+str(time.time_ns())+'.sh')
        p.write_text('set -eu\n'+text)
        return p

    def launch(self,text,name='job',*options):
        out=self.base/name
        result=self.call(self.payload,'--run',self.script(text),'--output',out,*options)
        job=json.loads((out/'remote_job.json').read_text())['job']
        return result,out,job

    def test_send_receive_trailing_slash_and_quotes(self):
        source=self.base/"directory ' quoted"
        source.mkdir();(source/'data').write_bytes(b'\x00\xffabc')
        result=self.call(str(source)+'/','--send')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.root/'projects/vins'/source.name/'data').read_bytes(),b'\x00\xffabc')
        result=self.call('projects/vins/'+source.name+'/','--receive','--dest',self.base/'download')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.base/'download'/source.name/'data').read_bytes(),b'\x00\xffabc')

    def test_send_uses_selected_working_directory(self):
        cwd=self.root/"field project ' quoted"
        result=self.call(self.payload,'--send','--cwd',cwd)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((cwd/self.payload.name).read_bytes(),self.payload.read_bytes())
        self.assertFalse((self.root/'incoming').exists())

    def test_named_job_refuses_reuse_and_path_escape(self):
        parent=self.root/"projects/vins/runs"
        result,out,job=self.launch('echo kept > logs/marker\n','named-first','--dest',parent,'--job-name','camera-calibration01')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(Path(job),parent/'camera-calibration01')
        again=self.call(self.payload,'--run',self.script('echo overwritten > logs/marker\n'),'--output',self.base/'second','--dest',parent,'--job-name','camera-calibration01')
        self.assertNotEqual(again.returncode,0)
        self.assertEqual((Path(job)/'logs/marker').read_text(),'kept\n')
        for name in ('', '../escape','/absolute','a/b','-option','x'*81):
            invalid=self.call(self.payload,'--run',self.script('true\n'),'--output',self.base/'invalid','--job-name',name)
            self.assertEqual(invalid.returncode,2,invalid.stderr)
            self.assertFalse((self.base/'invalid').exists())
        pulled=self.call(job,'--collect',self.base/'recovered')
        self.assertEqual(pulled.returncode,0,pulled.stderr)
        self.assertEqual((self.base/'recovered/marker').read_text(),'kept\n')

    def test_exec_environment_directory_arguments_and_exit(self):
        command="import os,sys;print(os.environ['TEST_REMOTE_ENV']);print(os.getcwd());print(sys.argv[1]);sys.exit(7)"
        result=self.call('--exec','--','python3','-c',command,"$(touch INJECTED) ' quoted")
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertEqual(result.stdout.splitlines(),['loaded',str(self.root/'projects/vins'),"$(touch INJECTED) ' quoted"])
        self.assertFalse((self.root/'projects/vins/INJECTED').exists())

    def test_live_events_nested_logs_and_failure_collection(self):
        out=self.base/'live'
        script=self.script('vins_event INPUT_READY ready\nmkdir -p logs/nested\necho first > logs/nested/vins.log\nsleep 2\necho second >> logs/nested/vins.log\nexit 7\n')
        p=subprocess.Popen(self.args(self.payload,'--run',script,'--output',out),env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        lines=[]; arrivals=queue.Queue()
        def reader():
            for line in p.stdout:lines.append(line);arrivals.put(line)
        t=threading.Thread(target=reader);t.start()
        deadline=time.monotonic()+10
        while True:
            line=arrivals.get(timeout=max(.1,deadline-time.monotonic()))
            if '[nested/vins.log] first' in line:break
        self.assertIsNone(p.poll(),'Log did not arrive until task completion')
        code=p.wait(timeout=20);t.join(timeout=3)
        self.assertEqual(code,7,p.stderr.read())
        self.assertIn('[INPUT_READY] ready',''.join(lines))
        self.assertIn('second',(out/'nested/vins.log').read_text())
        self.assertEqual((out/'exit_code').read_text().strip(),'7')
        p.stdout.close();p.stderr.close()

    def test_json_events_only(self):
        result,out,_=self.launch('vins_event PROBE_OK done\necho raw-log\n','json','--events-only')
        self.assertEqual(result.returncode,0,result.stderr)
        events=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertIn('PROBE_OK',[e['code'] for e in events])
        self.assertEqual(events[-1]['code'],'JOB_FINISHED')
        self.assertIn('raw-log',(out/'console.log').read_text())

    def test_timeout_cleanup(self):
        result,out,_=self.launch("trap 'echo cleaned > logs/cleaned; exit 0' INT TERM\nwhile :; do sleep 1; done\n",'timeout','--timeout','1')
        self.assertEqual(result.returncode,124,result.stdout+result.stderr)
        self.assertTrue((out/'cleaned').exists())
        self.assertEqual(json.loads((out/'result.json').read_text())['status'],'timeout')

    def test_detach_stop_and_recollect_same_receipt(self):
        result,out,job=self.launch("trap 'echo cleaned > logs/cleaned; exit 0' INT TERM\nwhile :; do sleep 1; done\n",'stop','--detach')
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.call(job,'--stop','--output',out)
        self.assertEqual(result.returncode,130,result.stdout+result.stderr)
        self.assertEqual(json.loads((out/'result.json').read_text())['status'],'cancelled')
        result=self.call(job,'--collect',out)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_disconnect_reconnect_does_not_rerun(self):
        result,out,job=self.launch('echo unique >> logs/started\nsleep 2\n','disconnect','--detach')
        self.assertEqual(result.returncode,0,result.stderr)
        bad=self.call(job,'--follow',env=dict(self.env,FAKE_DISCONNECT='1'))
        self.assertEqual(bad.returncode,255,bad.stderr)
        recovered=self.call(job,'--follow','--output',out)
        self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
        self.assertEqual((out/'started').read_text(),'unique\n')

    def test_finished_exit_130_is_collected(self):
        result,out,_=self.launch('exit 130\n','exit130')
        self.assertEqual(result.returncode,130,result.stderr)
        self.assertTrue((out/'result.json').exists())

    def test_ctrl_c_detaches_only(self):
        out=self.base/'interrupt'
        p=subprocess.Popen(self.args(self.payload,'--run',self.script('echo unique >> logs/started\nsleep 3\n'),'--output',out,'--events-only'),
                           env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        # Receipt precedes upload/worker start; wait for an actual task event.
        event=json.loads(p.stdout.readline())
        self.assertEqual(event['code'],'JOB_STARTED')
        os.killpg(p.pid,signal.SIGINT)
        p.wait(timeout=10);p.stdout.close();p.stderr.close()
        job=json.loads((out/'remote_job.json').read_text())['job']
        recovered=self.call(job,'--follow','--output',out)
        self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
        self.assertEqual((out/'started').read_text(),'unique\n')

    def test_missing_environment_and_no_env_escape(self):
        (self.root/'install/env.sh').unlink()
        result=self.call('--exec','--','true')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Missing environment',result.stderr)
        result=self.call('--exec','--no-env','--','printf','%s','works')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'works')

    def test_command_options_are_not_client_options(self):
        result=self.call('--exec','--','printf','%s|%s','--config','not-a-client-config')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'--config|not-a-client-config')

    def test_reject_existing_output_and_conflicting_modes(self):
        out=self.base/'existing';out.mkdir();(out/'keep').write_text('safe')
        result=self.call(self.payload,'--run',self.script('true'),'--output',out)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((out/'keep').read_text(),'safe')
        result=self.call(self.payload,'--send','--receive')
        self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()
