"""One host interface; transport uses OpenSSH and rsync."""
import argparse,hashlib,json,os,shlex,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'runtime'),str(ROOT/'buildkit')]
from common import load,atomic,digest,dataset_files

def call(args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)
def transport(c):
    a=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','-p',str(c['board']['ssh_port'])]
    if c['board']['identity_file']:a+=['-i',str(Path(c['board']['identity_file']).expanduser())]
    return a

def rpc(c,code,args=()):
    cmd=['/usr/bin/python3','-',*map(str,args)] if c.get('_host') else [*transport(c),c['board']['target'],'python3 - '+shlex.join(list(map(str,args)))]
    try:return json.loads(call(cmd,input=code,text=True,capture_output=True).stdout)
    except subprocess.CalledProcessError as e:raise RuntimeError('目标端请求失败：'+(e.stderr or str(e)).strip()) from e

def shell(c,script,capture=True):
    cmd=['bash','-c',script] if c.get('_host') else [*transport(c),c['board']['target'],script]
    try:r=call(cmd,text=True,capture_output=capture)
    except subprocess.CalledProcessError as e:raise RuntimeError('目标端步骤失败：'+(e.stderr or str(e)).strip()) from e
    return json.loads(r.stdout) if capture else r

def sync(c,source,dest,receive=False,exclude_logs=False,exclude_raw=False):
    src,dst=str(source),str(dest)
    if not c.get('_host'):
        remote=c['board']['target']+':'+dst
        src,dst=(remote,src) if receive else (src,remote)
    elif receive:src,dst=dst,src
    call(['rsync','-a','--partial','--protect-args','--info=progress2',*(['--exclude=*.log','--exclude=ros-logs/','--exclude=ros-home/'] if exclude_logs else []),*(['--exclude=raw/'] if exclude_raw else []),*(['-e',shlex.join(transport(c))] if not c.get('_host') else []),src,dst])

def workspace(c):
    value=str(ROOT/'build/host/workspace') if c.get('_host') else c['board']['workspace']
    return rpc(c,"import os,sys,json;p=os.path.abspath(os.path.expanduser(sys.argv[1]));assert p not in ['/',os.path.expanduser('~')];os.makedirs(p,exist_ok=True);print(json.dumps(p))",[value])

def package_fingerprint():
    paths=[ROOT/'project.example.yaml']
    for d in ['runtime','buildkit','vins_estimator','camera_models','third_party']:
        paths += [p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)},sort_keys=True).encode()).hexdigest()

def build(c):
    target='host' if c.get('_host') else 'board';log=Path(c['paths']['build'])/(target+'-build.log');log.parent.mkdir(parents=True,exist_ok=True)
    from fetch import sources
    sources()
    if target=='board':
        from hardware import prepare
        prepare(lambda item,dest:sync(c,dest,item['board_seed'],True))
    input_fingerprint=package_fingerprint()
    print('[构建] '+target+'；日志 '+str(log),flush=True)
    with log.open('w') as f:
        p=subprocess.Popen(['/usr/bin/python3',str(ROOT/'buildkit/build.py'),'--target',target,'--jobs',str(c['build']['jobs'])],stdout=f,stderr=subprocess.STDOUT)
        updated=0
        while p.poll() is None:
            time.sleep(1)
            if time.monotonic()-updated>10:
                lines=log.read_text(errors='replace').splitlines();progress=next((s for s in reversed(lines) if s.startswith(('[','+ cmake','BUILD'))),'准备依赖')
                print('[构建进度] '+progress[:160],flush=True);updated=time.monotonic()
        if p.returncode:raise RuntimeError('Build failed; '+str(log)+'\n'+'\n'.join(log.read_text(errors='replace').splitlines()[-12:]))
    if target=='board':
        print('[构建] 相机/IMU 适配器',flush=True)
        with log.open('a') as f:call(['/usr/bin/python3',str(ROOT/'buildkit/hardware.py')],stdout=f,stderr=subprocess.STDOUT)
    from bundle import bundle
    r=bundle(target)
    if package_fingerprint()!=input_fingerprint:raise RuntimeError('构建期间源码发生变化；当前包保留供核查，请重新 build/run，避免部署混合版本')
    r['input_fingerprint']=input_fingerprint;atomic(ROOT/'releases'/(target+'.json'),r);return r

def ensure(c):
    target='host' if c.get('_host') else 'board';p=ROOT/'releases'/(target+'.json')
    if p.exists():
        r=json.loads(p.read_text())
        if r.get('input_fingerprint')==package_fingerprint() and Path(r['archive']).is_file() and digest(r['archive'])==r['sha256']:return r
    return build(c)

def preflight(c):
    if not shutil.which('rsync') or not shutil.which('ssh'):raise ValueError('主机需要 OpenSSH 和 rsync')
    if c['run']['mode']=='sensor':
        if c.get('_host'):raise ValueError('真实设备只在板端验证；主机请选择 run.mode=replay')
        from common import camera_settings
        hw=camera_settings(c)
        print('[硬件] FLIR {} | binning {} | crop {} | trigger {} | GNW {}'.format(hw['serial'],hw['binning'],hw['crop'],hw['trigger'],c['inputs']['imu']['device']['port']),flush=True)
        if hw['binning']!=2 or hw['crop']!=[256,128,512,512]:print('[注意] 图像几何已偏离旧现场标定，请核对 calibration 与外参后运行',flush=True)
        return
    from rosbags.rosbag1 import Reader
    from rosbags.typesys import Stores,get_typestore
    files=dataset_files(c);topics={c['inputs']['camera']['topic']:'sensor_msgs/msg/Image',c['inputs']['imu']['topic']:'sensor_msgs/msg/Imu'}
    seen=set();found=set();starts=[];ends=[];store=get_typestore(Stores.ROS1_NOETIC)
    for path in files:
        with Reader(path) as r:
            starts.append(r.start_time);ends.append(r.end_time)
            connections=[x for x in r.connections if x.topic in topics]
            for conn in connections:
                if conn.msgtype!=topics[conn.topic]:raise ValueError('话题类型错误：'+conn.topic)
                found.add(conn.topic)
            for conn,stamp,data in r.messages(connections=connections):
                if conn.topic in seen:continue
                m=store.deserialize_ros1(data,conn.msgtype)
                if conn.msgtype.endswith('/Image'):
                    cam=c['inputs']['camera']
                    if (m.width,m.height)!=(cam['width'],cam['height']) or m.encoding not in [cam['encoding'],'8UC1']:raise ValueError('图像尺寸/编码与配置不匹配：'+conn.topic)
                seen.add(conn.topic)
                if len(seen)==2:break
    if found!=set(topics) or seen!=set(topics):raise ValueError('数据集图像/IMU话题缺失或为空')
    duration=(max(ends)-min(starts))/1e9
    if c['dataset']['start_s']>=duration:raise ValueError('dataset.start_s 超出数据时长')
    print('[数据] {} 文件 | {:.2f}s | 图像/IMU 首帧通过'.format(len(files),duration),flush=True)

def deploy(c):
    r=ensure(c);ws=workspace(c);ident=r['id'];archive=ws+'/incoming/'+ident+'.tar.gz';dest=ws+'/releases/'+ident
    if c.get('_host'):
        install=r['install']
        if shutil.disk_usage(install).free<c['run']['min_free_gib']*2**30:raise ValueError('主机剩余空间不足，需保留 '+str(c['run']['min_free_gib'])+' GiB')
        print('[主机运行包] 直接使用已校验的不可变 install，避免重复复制',flush=True)
    else:
        rpc(c,"import os,sys,json;os.makedirs(sys.argv[1],exist_ok=True);print('true')",[ws+'/incoming'])
        print('[上传运行包] '+ident,flush=True);sync(c,r['archive'],archive)
        code='''import hashlib,json,os,sys,tarfile,shutil
archive,dest,want,reserve=sys.argv[1:];h=hashlib.sha256()
with open(archive,'rb') as f:
 for b in iter(lambda:f.read(1048576),b''):h.update(b)
if h.hexdigest()!=want:raise ValueError('Archive SHA256 mismatch')
with tarfile.open(archive) as t:
 members=t.getmembers();size=sum(x.size for x in members)
 if shutil.disk_usage(os.path.dirname(archive)).free<(0 if os.path.exists(dest) else size)+float(reserve)*2**30:raise ValueError('Insufficient disk space')
 for m in members:
  if m.name.startswith('/') or '..' in m.name.split('/') or m.issym() or m.islnk():raise ValueError('Unsafe archive member')
 if not os.path.exists(dest):
  staging=dest+'.partial';os.makedirs(staging,exist_ok=True);t.extractall(staging);os.rename(staging,dest)
print(json.dumps(dest+'/install'))
'''
        install=rpc(c,code,[archive,dest,r['sha256'],c['run']['min_free_gib']])
    print('[检查运行包] 文件校验与私有依赖',flush=True)
    shell(c,'source '+shlex.quote(install+'/env.sh')+' && python3 '+shlex.quote(install+'/runtime/local.py')+' check')
    rpc(c,"import os,sys,json;root,install=sys.argv[1:];tmp=root+'/current.new';\nif os.path.lexists(tmp):os.unlink(tmp)\nos.symlink(install,tmp);os.replace(tmp,root+'/current');os.makedirs(root+'/projects/vins',exist_ok=True);print('true')",[ws,install])
    print('[部署完成] '+install,flush=True);return ws,install

def installed(c,prepare=False):
    ws=workspace(c)
    found=rpc(c,"import os,sys,json;p=sys.argv[1]+'/current';print(json.dumps(os.path.realpath(p) if os.path.isfile(p+'/env.sh') else None))",[ws])
    if found:return ws,found
    if prepare:return deploy(c)
    raise ValueError('目标端尚无运行包；使用 ./vins deploy 或 run')

def control(c,action,job=None):
    if action=='status':
        # Status/ recovery must also work when current is absent or corrupt.
        import inspect
        from local import state as local_state
        code="import json,os,sys\nfrom pathlib import Path\nTERMINAL={'completed','failed','cancelled'}\n"+inspect.getsource(atomic)+'\n'+inspect.getsource(local_state)+"\nprint(json.dumps(state(Path(sys.argv[1]))))"
        return rpc(c,code,[workspace(c)])
    ws,install=installed(c)
    text='source '+shlex.quote(install+'/env.sh')+' && python3 '+shlex.quote(install+'/runtime/local.py')+' --workspace '+shlex.quote(ws)+' '+action
    if job:text+=' '+shlex.quote(job)
    return shell(c,text)

def collect(c,raw=False):
    ws,install=installed(c);active=rpc(c,"import sys;print(open(sys.argv[1]+'/active.json').read())",[ws]);remote=active['job'];s=control(c,'status')
    if s['phase'] not in ['completed','failed','cancelled']:raise RuntimeError('任务仍在运行，先 stop 或等待结束')
    submitted=rpc(c,"import sys;print(open(sys.argv[1]+'/project.json').read())",[remote])
    target='host' if c.get('_host') else 'board';task=Path(s['task']);dest=Path(submitted['paths']['experiments'])/task.parent/target/task.name;dest.mkdir(parents=True,exist_ok=True)
    want_raw=raw or submitted['results']['raw_data']=='always'
    print('[回收] '+str(dest),flush=True);sync(c,str(dest)+'/',remote+'/',True,submitted['results']['raw_logs']=='none',not want_raw)
    manifest=json.loads((dest/'files.json').read_text())
    selected={name:want for name,want in manifest.items() if want_raw or not name.startswith('raw/')}
    for name,want in selected.items():
        if digest(dest/name)!=want:raise RuntimeError('回传文件校验失败：'+name)
    atomic(dest/'transfer.json',dict(verified_files=len(selected),raw_data_collected=want_raw,source=remote,task=s['task']))
    if submitted['run']['mode']=='replay' and submitted['dataset']['ground_truth']:
        from evaluate import evaluate
        try:atomic(dest/'evaluation.json',evaluate(dest/'vio.csv',Path(submitted['dataset']['ground_truth'])))
        except (ValueError,OSError) as e:
            atomic(dest/'evaluation.json',dict(status='unavailable',reason=str(e)))
            if s['phase']=='completed':raise RuntimeError('回收已完成，精度评估失败：'+str(e)) from e
    print('[回收校验完成] {} 文件；{}'.format(len(selected),dest),flush=True);return dest

def show(s):
    text='[{}] {}'.format(s['phase'],s.get('task',''))
    if s.get('observation'):
        o=s['observation'];text+=' | 图像 {:.1f}Hz | IMU {:.1f}Hz | 位姿 {} ({:.2f},{:.2f},{:.2f})'.format(o['image']['hz'],o['imu']['hz'],o['pose']['count'],*o['position_m'])
    if s.get('bag') and s.get('observation'):
        row=s['bag']['topics'][next(t for t,v in s['bag']['topics'].items() if v['type']=='sensor_msgs/Image')];stamp=s['observation']['image']['stamp_ns']
        text+=' | {:.0f}%'.format(max(0,min(100,100*(stamp-row['first_ns'])/max(1,row['last_ns']-row['first_ns']))))
    print(text+' | WARN/ERROR '+str(sum(v['count'] for v in s.get('warnings',{}).values())),flush=True)
    if s.get('error'):print('原因：'+s['error'],flush=True)

def follow(c,collect_result=False):
    try:
        last_notice=0;last_count=-1
        while True:
            s=control(c,'status');show(s)
            count=sum(v['count'] for v in s.get('warnings',{}).values())
            if count!=last_count and time.monotonic()-last_notice>=c['monitor']['repeat_notice_s']:
                for name,row in s.get('warnings',{}).items():print('[告警] {} ×{} {}'.format(name,row['count'],row['last']),flush=True)
                last_notice=time.monotonic();last_count=count
            if s['phase'] in ['completed','failed','cancelled','idle']:
                if collect_result and s['phase']!='idle' and c['results']['collect']:collect(c)
                return s.get('exit_code',0)
            time.sleep(c['monitor']['refresh_s'])
    except KeyboardInterrupt:print('\n已退出查看，任务继续运行；使用 ./vins status / stop / pull',flush=True);return 0

def run(c,background=False,record_only=False):
    preflight(c)
    active=control(c,'status')
    if active['phase'] not in ['idle','completed','failed','cancelled']:raise RuntimeError('已有活动任务：'+active.get('task','unknown'))
    ws,install=deploy(c)
    if c['run']['mode']=='replay':
        files=dataset_files(c);hashes={p.name:digest(p) for p in files};ident=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
        path=Path(c['dataset']['bag']);remote=str(path) if c.get('_host') else ws+'/data/'+path.stem+'-'+ident+('' if path.is_dir() else '.bag')
        hash_code="import os,sys,json,hashlib;p=sys.argv[1];os.makedirs(os.path.dirname(p),exist_ok=True);\nif os.path.isfile(p):\n h=hashlib.sha256();f=open(p,'rb')\n for b in iter(lambda:f.read(1048576),b''):h.update(b)\n print(json.dumps(h.hexdigest()))\nelse:print('null')"
        for source in files:
            destination=remote+'/'+source.name if path.is_dir() else remote
            if rpc(c,hash_code,[destination])==hashes[source.name]:continue
            rpc(c,"import os,sys,json,shutil;p,size,reserve=sys.argv[1:];free=shutil.disk_usage(os.path.dirname(p)).free;assert free>int(size)+float(reserve)*2**30,'Insufficient disk space for dataset';print('true')",[destination,source.stat().st_size,c['run']['min_free_gib']])
            print('[上传数据] '+source.name,flush=True);sync(c,source,destination)
            if rpc(c,hash_code,[destination])!=hashes[source.name]:raise RuntimeError('数据传输校验失败')
    else:hardware_preflight(c,install,ws)
    name=c['run']['name'];job=rpc(c,"import os,sys,json;root=sys.argv[1];os.makedirs(root,exist_ok=True);i=1\nwhile True:\n p=root+'/'+str(i).zfill(3)\n try:os.mkdir(p);break\n except FileExistsError:i+=1\nprint(json.dumps(p))",[ws+'/experiments/'+name])
    submitted=json.loads(json.dumps(c));submitted['dataset']['bag']=remote if c['run']['mode']=='replay' else None;submitted['_record_only']=record_only;submitted.update(_workspace=ws,_task=name+'/'+Path(job).name)
    taskfile=Path(c['paths']['cache'])/'submissions'/(hashlib.sha256((ws+'|'+job).encode()).hexdigest()+'.json');atomic(taskfile,submitted);sync(c,taskfile,job+'/project.json');show(control(c,'start',job))
    return 0 if background else follow(c,True)

def hardware_preflight(c,install,ws):
    checked=json.loads(json.dumps(c));checked['_workspace']=ws
    script='import json,sys;from common import check_hardware;print(json.dumps(check_hardware(json.loads(sys.argv[1]),sys.argv[2])))'
    text='source '+shlex.quote(install+'/env.sh')+' && PYTHONPATH='+shlex.quote(install+'/runtime')+':"$PYTHONPATH" python3 -c '+shlex.quote(script)+' '+shlex.quote(json.dumps(checked))+' '+shlex.quote(install)
    result=shell(c,text);print('[硬件检查] '+json.dumps(result,ensure_ascii=False),flush=True);return result

def main():
    p=argparse.ArgumentParser(prog='./vins',description='VINS 开环实验平台：一份配置、主机构建、板端运行');p.add_argument('-c','--config',default=str(ROOT/'project.yaml'));subs=p.add_subparsers(dest='cmd',required=True)
    for name in ['run','record','build','deploy','check','remote','status','stop','pull']:
        s=subs.add_parser(name,help={'record':'只采集原始数据，不启动 VINS','run':'准备并运行实验','build':'构建完整运行包','deploy':'推送并校验运行包','check':'检查数据和已部署包','remote':'进入已激活环境的 SSH 终端','status':'查看当前/最近任务','stop':'正常停止并回收','pull':'补收并校验结果'}[name]);s.add_argument('--host',action='store_true',help='操作主机验证环境，默认板端')
        if name in ['run','record']:s.add_argument('--background',action='store_true')
        if name=='pull':s.add_argument('--raw',action='store_true',help='包含原始实采 bag，忽略 on_request 策略')
        if name=='status':s.add_argument('--follow',action='store_true')
        if name=='build':s.add_argument('--target',choices=['host','board'])
    a=p.parse_args();c=load(a.config);c['_host']=a.host or (a.cmd=='build' and a.target=='host')
    if a.cmd=='build':build(c)
    elif a.cmd=='deploy':deploy(c)
    elif a.cmd=='check':
        preflight(c);ws,install=installed(c)
        if c['run']['mode']=='sensor':hardware_preflight(c,install,ws)
        else:print(json.dumps(shell(c,'source '+shlex.quote(install+'/env.sh')+' && python3 '+shlex.quote(install+'/runtime/local.py')+' check'),ensure_ascii=False))
    elif a.cmd in ['run','record']:
        if a.cmd=='record' and c['run']['mode']!='sensor':raise ValueError('record 需要 run.mode=sensor')
        return run(c,a.background,a.cmd=='record')
    elif a.cmd=='status':
        if a.follow:return follow(c)
        show(control(c,'status'))
    elif a.cmd=='stop':
        s=control(c,'status')
        if s['phase'] in ['idle','completed','failed','cancelled']:show(s);return 0
        control(c,'stop');follow(c,True);return 0
    elif a.cmd=='pull':collect(c,a.raw)
    else:
        ws,install=installed(c,True);s=control(c,'status')
        if s['phase'] not in ['idle','completed','failed','cancelled']:install=s.get('install',install)
        text='cd '+shlex.quote(ws+'/projects/vins')+' && source '+shlex.quote(install+'/env.sh')+' && export ROS_MASTER_URI='+shlex.quote(s.get('master_uri','http://127.0.0.1:11311') if s['phase'] not in ['idle','completed','failed','cancelled'] else 'http://127.0.0.1:11311')+' && exec bash --noprofile --norc'
        call(['bash','-c',text] if c.get('_host') else [*transport(c),'-t',c['board']['target'],text])
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError,subprocess.CalledProcessError) as e:print('错误：'+str(e),file=sys.stderr);sys.exit(1)
