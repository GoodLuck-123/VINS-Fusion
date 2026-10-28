"""Configuration invariants: prevent unsafe/misleading runs before transport."""
import copy,sys,tempfile,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import load,effective
class ConfigTests(unittest.TestCase):
    def setUp(self):self.source=yaml.safe_load((ROOT/'tests/fixtures/euroc.yaml').read_text())
    def check_rejected(self,change):
        c=copy.deepcopy(self.source)
        for key in ['cache','build','releases']:c['paths'][key]=str(ROOT/key)
        change(c)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'project.yaml';p.write_text(yaml.safe_dump(c))
            with self.assertRaises(ValueError):load(p)
    def test_real_transform_direction(self):
        c=copy.deepcopy(self.source)
        for key in ['cache','build','releases']:c['paths'][key]=str(ROOT/key)
        with tempfile.TemporaryDirectory() as d:
            effective(c,Path(d));s=(Path(d)/'vins.yaml').read_text()
            self.assertIn('0.00981073058949',s);self.assertNotIn('-0.00981073058949',s)
    def test_hardware_template(self):
        c=load(ROOT/'project.example.yaml');self.assertEqual(c['run']['mode'],'sensor');self.assertEqual(c['inputs']['camera']['device']['trigger'],'hardware')
    def test_bad_rate(self):self.check_rejected(lambda c:c['dataset'].update(rate=float('nan')))
    def test_bad_start(self):self.check_rejected(lambda c:c['dataset'].update(start_s=float('nan')))
    def test_monitor_flag(self):self.check_rejected(lambda c:c['monitor'].update(enabled='yes'))
    def test_mono_needs_imu(self):self.check_rejected(lambda c:c['inputs']['imu'].update(enabled=False))
    def test_no_path_in_task_name(self):self.check_rejected(lambda c:c['run'].update(name='../../other'))
    def test_matrix_must_be_rotation(self):self.check_rejected(lambda c:c['vins']['body_T_cam0'][0].__setitem__(0,2))
    def test_positive_dimensions(self):self.check_rejected(lambda c:c['inputs']['camera'].update(width=0))
    def test_units_are_explicit(self):self.check_rejected(lambda c:c['inputs']['imu'].update(angular_velocity_unit='deg/s'))
    def test_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.yaml';p.write_text('schema_version: 1\nschema_version: 2\n')
            with self.assertRaises(ValueError):load(p)
if __name__=='__main__':unittest.main()
