"""User-facing hardware mistakes must fail before deployment/acquisition."""
import copy,sys,tempfile,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import load,dataset_files
class HardwareConfigTests(unittest.TestCase):
    def rejected(self,change):
        c=yaml.safe_load((ROOT/'project.example.yaml').read_text())
        for k in ['cache','build','releases']:c['paths'][k]=str(ROOT/k)
        change(c)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.yaml';p.write_text(yaml.safe_dump(c))
            with self.assertRaises(ValueError):load(p)
    def test_crop_outside(self):self.rejected(lambda c:c['inputs']['camera']['device'].update(crop=[900,0,512,512]))
    def test_trigger_typo(self):self.rejected(lambda c:c['inputs']['camera']['device'].update(trigger='hard'))
    def test_bad_binning(self):self.rejected(lambda c:c['inputs']['camera']['device'].update(binning=True))
    def test_bad_exposure(self):self.rejected(lambda c:c['inputs']['camera']['device']['exposure'].update(auto_max_us=float('nan')))
    def test_wrong_sensor_calibration(self):self.rejected(lambda c:c['inputs']['camera']['calibration'].update(verified_for='euroc-cam0'))
    def test_recording_required(self):self.rejected(lambda c:c['recording'].update(enabled=False))
    def test_deadline_before_capture_end(self):self.rejected(lambda c:c['run'].update(duration_s=700))
    def test_open_recording_not_replayed(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'capture.bag').touch();(Path(d)/'other.bag.active').touch()
            with self.assertRaises(ValueError):dataset_files({'dataset':{'bag':d}})
if __name__=='__main__':unittest.main()
