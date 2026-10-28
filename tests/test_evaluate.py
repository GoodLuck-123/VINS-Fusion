import csv,sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluate import evaluate
class EvaluationTests(unittest.TestCase):
    def files(self,d,scale=1):
        points=[[0,0,0],[1,0,0],[1,2,0],[0,2,1],[2,3,1]]
        a=Path(d)/'estimate.csv';b=Path(d)/'truth.csv'
        with a.open('w') as f,b.open('w') as g:
            for i,(x,y,z) in enumerate(points):
                stamp=1400000000000000000+i*100000000
                csv.writer(f).writerow([stamp,scale*x,scale*y,scale*z,1,0,0,0])
                # Rotate 90deg and translate; quaternion is the same world alignment.
                csv.writer(g).writerow([stamp,-y+5,x-2,z+3,np.sqrt(.5),0,0,np.sqrt(.5)])
        return a,b
    def test_known_rigid_transform(self):
        with tempfile.TemporaryDirectory() as d:
            result=evaluate(*self.files(d));self.assertLess(result['ate_m']['rmse'],1e-12);self.assertLess(result['rpe_m']['rmse'],1e-12);self.assertEqual(result['matched'],5)
    def test_scale_error_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as d:self.assertGreater(evaluate(*self.files(d,scale=1.1))['ate_m']['rmse'],.05)
