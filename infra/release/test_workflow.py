"""Exercise deployment refusal, archive validation, quoting and log collection locally."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vins workflow ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'board home'
        self.home.mkdir()
        self.tool = self.root / 'remote'
        self.tool.write_text('''#!/usr/bin/env python3
import os, pathlib, shutil, subprocess, sys, tempfile
args=sys.argv[1:]
if '--print-config' in args:
 import json
 root=args[args.index('--root')+1] if '--root' in args else 'vins-workspace'
 print(json.dumps(dict(target='user@board',root=root,cwd=root+'/projects/vins',env=root+'/install/env.sh')))
 sys.exit(0)
output=pathlib.Path(args[args.index('--output')+1])
if '--job-name' in args:
 parent=pathlib.Path(args[args.index('--dest')+1])
 if not parent.is_absolute():parent=pathlib.Path(os.environ['HOME'])/parent
 parent.mkdir(parents=True,exist_ok=True)
 job=parent/args[args.index('--job-name')+1]
 job.mkdir()
else:job=pathlib.Path(tempfile.mkdtemp(dir=os.environ['HOME']))
(job/'logs').mkdir()
env=dict(os.environ,VINS_REMOTE_ROOT=str(job),VINS_REMOTE_PAYLOAD=str(pathlib.Path(args[1]).resolve()))
code=subprocess.run(['bash',args[args.index('--run')+1]],env=env).returncode
shutil.copytree(job/'logs',output)
sys.exit(code)
''')
        self.tool.chmod(0o755)
        self.archive = self.root / 'install.tar.gz'
        files = {
            'release.json': json.dumps(dict(ros='ros1', version='v0.1')).encode(),
            'bin/vins': b'#!/usr/bin/env bash\nset -eu\nif test "$1" = check; then mkdir -p "$2"; echo checked > "$2/result"; else mkdir -p "$3"; printf "%s" "$2" > "$3/bag_path"; fi\n',
        }
        sums = ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name, data in files.items()).encode()
        files['SHA256SUMS'] = sums
        with tarfile.open(self.archive, 'w:gz') as tar:
            for name, data in files.items():
                info = tarfile.TarInfo('install/'+name)
                info.size = len(data)
                info.mode = 0o755 if name == 'bin/vins' else 0o644
                tar.addfile(info, io.BytesIO(data))
        self.checksum = self.archive.with_name(self.archive.name+'.sha256')
        self.checksum.write_text(hashlib.sha256(self.archive.read_bytes()).hexdigest()+'  install.tar.gz\n')

    def invoke(self, script, *args):
        return subprocess.run([sys.executable,str(HERE/script),'user@board',*map(str,args),'--tool',str(self.tool),*(['--name','test-'+Path(str(args[-1])).name.replace(' ','-')] if script == 'run.py' else [])],
                              env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)

    def test_deploy_then_check_and_replay_request(self):
        result=self.invoke('deploy.py',self.archive,'--output',self.root/'deploy logs')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.home/'vins-workspace/releases/ros1-v0.1/install/bin/vins').exists())
        result=self.invoke('run.py','--output',self.root/'check logs')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.root/'check logs/runtime-check/result').read_text().strip(),'checked')
        bag="/data/a bag 'quote' $(touch SHOULD_NOT_EXIST).bag"
        result=self.invoke('run.py','--bag',bag,'--output',self.root/'replay logs')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.root/'replay logs/experiment/bag_path').read_text(),bag)
        self.assertFalse((HERE/'SHOULD_NOT_EXIST').exists())

    def test_named_run_and_duplicate_refusal(self):
        self.assertEqual(self.invoke('deploy.py',self.archive,'--output',self.root/'deploy').returncode,0)
        common=['--tool',str(self.tool)]
        def run(name, output):
            return subprocess.run([sys.executable,str(HERE/'run.py'),'--name',name,'--output',str(output),*common],env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        first=run('field-check01',self.root/'first')
        self.assertEqual(first.returncode,0,first.stderr)
        marker=self.home/'vins-workspace/projects/vins/runs/field-check01/logs/runtime-check/result'
        self.assertEqual(marker.read_text().strip(),'checked')
        self.assertNotEqual(run('field-check01',self.root/'second').returncode,0)
        self.assertEqual(marker.read_text().strip(),'checked')
        self.assertEqual(run('../escape',self.root/'invalid').returncode,2)
        default=subprocess.run([sys.executable,str(HERE/'run.py'),'--output',str(self.root/'sensor-check02'),*common],env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        self.assertEqual(default.returncode,0,default.stderr)
        self.assertTrue((marker.parents[3]/'sensor-check02/logs/runtime-check/result').exists())

    def test_existing_install_is_not_replaced(self):
        first=self.invoke('deploy.py',self.archive,'--output',self.root/'first')
        self.assertEqual(first.returncode,0,first.stderr)
        sentinel=self.home/'vins-workspace/releases/ros1-v0.1/install/user-file'
        sentinel.write_text('keep')
        again=self.invoke('deploy.py',self.archive,'--output',self.root/'second')
        self.assertNotEqual(again.returncode,0)
        self.assertEqual(sentinel.read_text(),'keep')

    def test_bad_sha_does_not_deploy(self):
        self.checksum.write_text('0'*64+'  install.tar.gz\n')
        result=self.invoke('deploy.py',self.archive,'--output',self.root/'bad sha')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.home/'vins-workspace').exists())

    def test_unsafe_archive_is_rejected(self):
        with tarfile.open(self.archive,'w:gz') as tar:
            info=tarfile.TarInfo('install/../../escape'); info.size=1
            tar.addfile(info,io.BytesIO(b'x'))
        result=self.invoke('deploy.py',self.archive,'--output',self.root/'unsafe')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.home/'vins-workspace').exists())

    def test_default_host_and_custom_workspace(self):
        root=self.home/"custom workspace ' quoted"
        common=['--tool',str(self.tool),'--root',str(root)]
        result=subprocess.run([sys.executable,str(HERE/'deploy.py'),str(self.archive),'--output',str(self.root/'custom deploy'),*common],
                              env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((root/'install').resolve(),root/'releases/ros1-v0.1/install')
        result=subprocess.run([sys.executable,str(HERE/'run.py'),'--output',str(self.root/'custom run'),'--name','custom-check',*common],
                              env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.root/'custom run/runtime-check/result').exists())

    def test_real_install_directory_is_preserved(self):
        real=self.home/'vins-workspace/install';real.mkdir(parents=True)
        (real/'keep').write_text('preserve')
        result=self.invoke('deploy.py',self.archive,'--output',self.root/'real directory')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(real.is_symlink())
        self.assertEqual((real/'keep').read_text(),'preserve')


if __name__ == '__main__':
    unittest.main()
