"""Freeze small, verified evidence after the released packages finish replay."""
import json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,digest
out=ROOT/'evidence/v0.1';out.mkdir(exist_ok=True);deadline=time.monotonic()+600
runs={'reference-host':'euroc-reference/host/001','patched-host':'euroc-mono/host/003','reference-board':'euroc-reference/board/001','patched-board':'euroc-mono/board/002','release-host':'euroc-final/host/002','release-board':'euroc-final/board/002'}
for key in ['release-host','release-board']:
 p=ROOT/'experiments'/runs[key]
 while not (p/'transfer.json').exists():
  assert time.monotonic()<deadline,'Final replay/transfer did not finish';time.sleep(1)
report={'implementation_commit':subprocess.check_output(['git','rev-parse','2062e82'],cwd=ROOT,text=True).strip(),'core_fix_commit':subprocess.check_output(['git','rev-parse','3d83b25'],cwd=ROOT,text=True).strip(),'runs':{},'packages':{},'frozen_refs':{}}
for label,rel in runs.items():
 p=ROOT/'experiments'/rel;s=json.loads((p/'state.json').read_text());e=json.loads((p/'evaluation.json').read_text());transfer=json.loads((p/'transfer.json').read_text())
 expected='failed' if label.startswith('reference') else 'completed';assert s['phase']==expected,(label,s)
 assert s['process_exits']['vins']==(-6 if label.startswith('reference') else 0),(label,s['process_exits'])
 assert s['initialization_log_count']==1 and s['trajectory_poses']==1831
 assert s['observation']['image']['count']==3682 and s['observation']['imu']['count']==36820
 for name,want in json.loads((p/'files.json').read_text()).items():assert digest(p/name)==want,(rel,name)
 dest=out/label;dest.mkdir(exist_ok=True)
 for name in ['state.json','evaluation.json','transfer.json','files.json','bag.json','vins.yaml','camera.yaml']:
  shutil.copy2(p/name,dest/name)
 row={'path':str(p),'state':s['phase'],'ate_rmse_m':e['ate_m']['rmse'],'rpe_rmse_m':e['rpe_m']['rmse'],'poses':s['trajectory_poses'],'vins_exit':s['process_exits']['vins'],'playback_wall_s':s['playback_wall_s'],'drain_s':s['drain_s'],'child_cpu_s':s['child_cpu_s'],'vins_resource_samples':s['resource_samples']['vins'],'observer_resource_samples':s['resource_samples']['observer'],'trajectory_sha256':digest(p/'vio.csv'),'state_sha256':digest(p/'state.json'),'verified_files':transfer['verified_files'],'package':s['install']}
 report['runs'][label]=row
for target in ['host','board']:
 r=json.loads((ROOT/'releases'/(target+'.json')).read_text());assert digest(r['archive'])==r['sha256'];r['manifest_sha256']=digest(Path(r['install'])/'files.json');report['packages'][target]=r
 label='release-'+target;s=json.loads((out/label/'state.json').read_text());assert Path(s['install']).parent.name==r['id']
for source,name in [(ROOT/'build/shutdown-validation/report.json','shutdown.json'),(ROOT/'build/lifecycle-validation/001/report.json','lifecycle.json')]:shutil.copy2(source,out/name)
for row in json.loads((ROOT/'evidence/intake/20261028/frozen-refs.json').read_text())['frozen_refs']:
 actual=subprocess.check_output(['git','rev-parse',row['ref']],cwd=ROOT,text=True).strip();assert actual==row['object'],row;report['frozen_refs'][row['ref']]=actual
assert report['runs']['reference-host']['trajectory_sha256']==report['runs']['patched-host']['trajectory_sha256']
atomic(out/'acceptance.json',report)
lines=['# v0.1 验收证据','','## Quick Start','','用户操作见 docs/03_USER_GUIDE.md；完整解释见 docs/04_VALIDATION.md。这里保存经过核验的小型记录；大轨迹和压缩日志保存在 experiments，不纳入 Git','','| 验证 | ATE RMSE m | RPE RMSE m | VINS 退出 | 回放 s | 收尾 s | 子进程 CPU s |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
for key,row in report['runs'].items():lines.append('| {} | {:.6f} | {:.6f} | {} | {:.3f} | {:.3f} | {:.3f} |'.format(key,row['ate_rmse_m'],row['rpe_rmse_m'],row['vins_exit'],row['playback_wall_s'],row['drain_s'],row['child_cpu_s']))
lines+=['','## 文件说明','','acceptance.json 关联精确包、归档 SHA256、构建/实现提交和任务；每个任务子目录有原始状态、评估协议、传输证明与实际参数。runtime-maps 证明私有库实际加载路径；lifecycle/shutdown/observer-inputs/package-checks/board-recovery 记录对应故障与迁移验证','','monitor-overhead 是同区间 30 秒的一次串行开关对照，只关闭话题观察器；任务监督和资源采样仍开启。CPU 总量是全部已等待子进程线程累计秒，per-process CPU 为采样下界，RSS/PSS 为观察峰值。未测整套监控（含主机 SSH 客户端）的全部成本，不将单次差异解释为性能收益','','未直接观测 VINS 内部处理队列；末帧覆盖与文件稳定不声明实时性。硬件采集、标定与同步质量留待 v0.2/v0.3，当前没有实际相机/IMU 算法通过的结论','']
(out/'README.md').write_text('\n'.join(lines))
files=[p for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'];(out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(out))+'\n' for p in files));print('ARCHIVED VERIFIED ACCEPTANCE',len(files),'files,',len(report['frozen_refs']),'frozen refs unchanged',flush=True)
