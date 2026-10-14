#!/usr/bin/env bash
set -euo pipefail
/usr/bin/python3 - <<'CHECK' > "$VINS_REMOTE_ROOT/logs/publication_audit.json"
import hashlib,json,os,pathlib
home=pathlib.Path.home();workspace=home/'vins-workspace';current=pathlib.Path(os.environ['VINS_REMOTE_ROOT']).resolve()
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
runtimes=[]
for name in ['jobs/1791960441164-99946/ros2-payload','jobs/1791961492786-103062/fastrtps-payload','jobs/1791970072506-133971/ros1-payload02']:
 root=workspace/name;manifest=json.loads((root/'files.json').read_text());changes=[]
 for relative,sha in manifest.items():
  if digest(root/relative)!=sha:changes.append(relative)
 runtimes.append(dict(root=str(root),files=len(manifest),manifest_sha256=digest(root/'files.json'),changed_files=changes))
jobs=[]
for job in sorted((workspace/'jobs').iterdir()):
 if not job.is_dir() or job.resolve()==current:continue
 logs=job/'logs'
 files={str(p.relative_to(logs)):digest(p) for p in logs.rglob('*') if p.is_file()}
 exit_path=logs/'exit_code'
 jobs.append(dict(job=job.name,exit_code=exit_path.read_text().strip() if exit_path.exists() else None,log_sha256=files))
git_dirs=[str(p) for p in workspace.rglob('.git')]
home_git_dirs=[str(p) for p in home.glob('*/.git')]
active=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:argv=(p/'cmdline').read_bytes().decode(errors='replace').split('\0')
 except OSError:continue
 if any(str(workspace/'jobs')+'/' in a for a in argv) and not any(str(current) in a for a in argv):active.append(dict(pid=int(p.name),argv=argv))
result=dict(runtimes=runtimes,jobs=jobs,git_dirs=git_dirs,home_git_dirs=home_git_dirs,active_prior_jobs=active,
            scope='Our deployed runtimes and job logs only; no SSH credentials read')
print(json.dumps(result,indent=2))
if active or git_dirs or any(r['changed_files'] for r in runtimes):raise SystemExit(1)
CHECK
