"""Failure-oriented local checks; actual ROS bags are validated on the board."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check
from common import Invalid, configuration, digest, directory, prepare_config
from run import Processes


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="board cli ' ")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'bin').mkdir()
        (self.root/'runtime/python38/bin').mkdir(parents=True)
        (self.root/'config/euroc').mkdir(parents=True)
        elf=bytearray(20);elf[:6]=b'\x7fELF\x02\x01';elf[18:20]=(183).to_bytes(2,'little')
        for name,data in {'bin/vins_node':bytes(elf),'runtime/python38/bin/python3':b'interpreter','bin/vins':b'entry','env.sh':b'env','release.json':json.dumps(dict(architecture='aarch64',ros='ros1',version='test')).encode(),'config/euroc/euroc_stereo_imu_config.yaml':b'config'}.items():
            (self.root/name).write_bytes(data)
        for name in ['bin/vins','bin/vins_node','runtime/python38/bin/python3']:(self.root/name).chmod(0o755)
        self.manifest()

    def manifest(self):
        (self.root/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(self.root))+'\n' for p in sorted(self.root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))

    def cli(self,*args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
            code=check.main(['--install',str(self.root),*map(str,args)])
        return code,out.getvalue()

    def test_composed_checks_keep_all_results(self):
        with patch('check.platform.machine',return_value='x86_64'):
            code,text=self.cli('--arc','--sha','--dir','--output',self.root/'future/output','--min-free-mb',0,'--json','-')
        self.assertEqual(code,1)
        report=json.loads(text)
        self.assertEqual([r['status'] for r in report['results']],['fail','pass','pass'])
        self.assertFalse((self.root/'future').exists())

    def test_architecture_includes_node_elf(self):
        with patch('check.platform.machine',return_value='aarch64'):
            self.assertEqual(self.cli('--arc')[0],0)
            (self.root/'bin/vins_node').write_bytes(b'wrong binary')
            self.assertEqual(self.cli('--arc')[0],1)

    def test_manifest_detects_missing_changed_and_escaped_files(self):
        self.assertEqual(self.cli('--sha')[0],0)
        (self.root/'bin/vins').write_text('changed')
        self.assertIn('SHA256 differs',self.cli('--sha')[1])
        (self.root/'bin/vins_node').unlink()
        self.assertIn('Missing file',self.cli('--sha')[1])
        (self.root/'SHA256SUMS').write_text('0'*64+'  ../outside\n')
        self.assertIn('Unsafe',self.cli('--sha')[1])

    def test_libraries_skip_relocatable_objects_and_detect_missing_soname(self):
        node=self.root/'bin/vins_node';header=bytearray(node.read_bytes());header[16:18]=(2).to_bytes(2,'little');node.write_bytes(header)
        folder=self.root/'runtime'
        header[16:18]=(1).to_bytes(2,'little');(folder/'python.o').write_bytes(header)
        with patch('check.environment',return_value=dict(os.environ)), patch('check.subprocess.run',return_value=subprocess.CompletedProcess([],0,'libc.so.6 => /lib/libc.so.6')) as ldd:
            self.assertEqual(self.cli('--lib')[0],0)
            self.assertEqual(ldd.call_count,1)
        with patch('check.environment',return_value=dict(os.environ)), patch('check.subprocess.run',return_value=subprocess.CompletedProcess([],0,'libmissing.so => not found')):
            self.assertIn('not found',self.cli('--lib')[1])

    def test_output_space_permission_and_existing_report(self):
        self.assertEqual(self.cli('--dir','--min-free-mb','1e20')[0],1)
        folder=self.root/'locked';folder.mkdir();folder.chmod(0o500)
        try:self.assertRaises(PermissionError,directory,folder,0)
        finally:folder.chmod(0o700)
        report=self.root/'report.json';report.write_text('keep')
        self.assertEqual(self.cli('--sha','--json',report)[0],1)
        self.assertEqual(report.read_text(),'keep')

    def config(self):
        repo=Path(__file__).resolve().parents[2]
        import shutil
        folder=self.root/'configuration';shutil.copytree(repo/'config/euroc',folder)
        return folder/'euroc_stereo_imu_config.yaml'

    def test_opencv_yaml_and_effective_copy(self):
        path=self.config()
        with self.assertRaisesRegex(Invalid,'absolute board path'):
            configuration(path,self.root)
        data=configuration(path,self.root,self.root/'output')
        self.assertEqual(len(data['topics']),3)
        output=self.root/"run output \\ ' 测试";output.mkdir()
        actual=prepare_config(data,output)
        reread=configuration(actual,self.root)
        self.assertEqual(reread['values']['body_T_cam0'],data['values']['body_T_cam0'])
        self.assertEqual(reread['values']['output_path'],str(output))
        self.assertTrue((actual.parent/'cam1.yaml').is_file())

    def test_invalid_yaml_ranges_rotation_and_calibration(self):
        path=self.config();original=path.read_text()
        for before,after in [('num_of_cam: 2','num_of_cam: 3'),('acc_n: 0.1','acc_n: -1'),('1.0 # ransac','0.0 # ransac')]:
            # The first two are guaranteed mutations in the canonical config.
            if before not in original:continue
            path.write_text(original.replace(before,after))
            with self.assertRaises(Invalid):configuration(path,self.root,self.root/'out')
        path.write_text(original+'\nimu: 1\n')
        with self.assertRaisesRegex(Invalid,'Duplicate'):configuration(path,self.root,self.root/'out')
        path.write_text(original);(path.parent/'cam0_mei.yaml').unlink()
        with self.assertRaisesRegex(Invalid,'Missing file'):configuration(path,self.root,self.root/'out')

    def test_owned_process_cleanup_preserves_other_process(self):
        unrelated=subprocess.Popen(['/usr/bin/python3','-c','import time;time.sleep(30)'],start_new_session=True)
        processes=Processes(self.root,dict(os.environ))
        try:
            child=processes.launch('owned',['/usr/bin/python3','-c','import time;time.sleep(30)'])
            exits=processes.stop()
            self.assertIsNotNone(child.poll())
            self.assertIsNotNone(exits['owned'])
            self.assertIsNone(unrelated.poll())
        finally:
            os.killpg(unrelated.pid,signal.SIGKILL);unrelated.wait()

    def test_no_selection_is_help_not_false_success(self):
        code,text=self.cli()
        self.assertEqual(code,2);self.assertIn('--arc',text)


if __name__=='__main__':unittest.main()
