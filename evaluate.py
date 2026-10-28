"""EuRoC body pose evaluation: timestamp association <=10ms, SE(3), no scale fit."""
import csv
from pathlib import Path
import numpy as np

def read(p):
    rows=[];stamps=[]
    with Path(p).open() as f:
        for row in csv.reader(l for l in f if l.strip() and not l.startswith('#')):
            stamps.append(int(row[0]));rows.append([float(x) for x in row[1:8]])
    a=np.asarray(rows)
    if len(stamps)<2 or a.shape!=(len(stamps),7) or not np.isfinite(a).all() or not all(x<y for x,y in zip(stamps,stamps[1:])):raise ValueError('Invalid trajectory: '+str(p))
    q=a[:,3:7];norm=np.linalg.norm(q,axis=1)
    if np.any(abs(norm-1)>.1):raise ValueError('Invalid quaternion norm: '+str(p))
    a[:,3:7]/=norm[:,None];return np.asarray(stamps,dtype=np.int64),a

def rotation(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def evaluate(estimate,truth):
    et,e=read(estimate);gt,g=read(truth);pairs=[];used=set()
    for i,t in enumerate(et):
        j=int(np.searchsorted(gt,t));candidates=[k for k in [j-1,j] if 0<=k<len(gt) and k not in used]
        if candidates:
            k=min(candidates,key=lambda x:abs(int(gt[x])-int(t)))
            if abs(int(gt[k])-int(t))<=10000000:pairs.append((i,k));used.add(k)
    if len(pairs)<3:raise ValueError('Insufficient EuRoC truth matches')
    ei,gi=np.asarray(pairs).T;x=e[ei,:3];y=g[gi,:3];mx=x.mean(0);my=y.mean(0)
    u,s,vt=np.linalg.svd((y-my).T@(x-mx));d=np.eye(3);d[2,2]=np.linalg.det(u@vt);r=u@d@vt;t=my-r@mx
    aligned=x@r.T+t;ate=np.linalg.norm(aligned-y,axis=1);rpe=[]
    for n in range(len(pairs)-1):
        est_delta=rotation(e[ei[n],3:]).T@(x[n+1]-x[n]);gt_delta=rotation(g[gi[n],3:]).T@(y[n+1]-y[n]);rpe.append(np.linalg.norm(est_delta-gt_delta))
    def stats(a):
        a=np.asarray(a);return dict(rmse=float(np.sqrt(np.mean(a*a))),mean=float(a.mean()),median=float(np.median(a)),max=float(a.max()))
    return dict(protocol='EuRoC IMU/body; nearest unique <=10ms; SE(3); scale fixed 1; adjacent matched pose translation RPE',poses=len(et),matched=len(pairs),first_ns=int(et[0]),last_ns=int(et[-1]),ate_m=stats(ate),rpe_m=stats(rpe),alignment_scale=1.0,alignment_rotation=r.tolist(),alignment_translation_m=t.tolist())
