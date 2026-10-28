"""Owned-process supervisor. State is durable; no dependency on the viewing SSH."""
import queue,fcntl,json,math,os,re,resource,signal,socket,subprocess,sys,tarfile,threading,time,xmlrpc.client
from pathlib import Path
from common import atomic,digest,effective,check_hardware,camera_settings,dataset_files

class Transport(xmlrpc.client.Transport):
    def make_connection(self,host):
        c=super().make_connection(host);c.timeout=1;return c

def supervise(job,install):
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    job=Path(job).resolve();install=Path(install).resolve();c=json.loads((job/'project.json').read_text());workspace=Path(c['_workspace'])
    lock=(workspace/'.run.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:atomic(job/'state.json',dict(phase='failed',exit_code=1,error='Another task is active'));return 1
    start=time.monotonic();state=dict(task=c['_task'],phase='starting',pid=os.getpid(),install=str(install),package=json.loads((install/'release.json').read_text()),events=[],warnings={},process_exits={},resource_samples={})
    sensor=c['run']['mode']=='sensor';record_only=c.get('_record_only',False);source_stopped=False;expected_end=set()
    children=[];threads=[];stop=[False];messages=queue.Queue();resource_start=resource.getrusage(resource.RUSAGE_CHILDREN)
    def event(code,message):
        item=dict(code=code,message=message,elapsed_s=time.monotonic()-start);state['events'].append(item)
        with (job/'events.jsonl').open('a') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
    def save():
        while not messages.empty():
            name,text=messages.get_nowait()
            if 'Initialization finish' in text:state['initialization_log_count']=state.get('initialization_log_count',0)+1
            else:
                level=re.search(r'\[\s*(WARN|ERROR|FATAL)\]',text)
                category='warning' if level and level[1]=='WARN' else 'error'
                if level and level[1]=='FATAL':state['fatal_log']=name+': '+text.strip()
                row=state['warnings'].setdefault(name+':'+category,dict(count=0,first_s=time.monotonic()-start))
                row.update(count=row['count']+1,last_s=time.monotonic()-start,last=text.strip()[-400:])
        state['elapsed_s']=time.monotonic()-start;state['heartbeat_monotonic']=time.monotonic();atomic(job/'state.json',state)
    def launch(name,args):
        f=(job/(name+'.log')).open('w');p=subprocess.Popen(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env=os.environ.copy());children.append((name,p))
        def read():
            try:
                for line in iter(p.stdout.readline,b''):
                    text=line.decode(errors='replace');f.write(text);f.flush()
                    if re.search(r'\[\s*(WARN|ERROR|FATAL)\]',text) or 'Initialization finish' in text:messages.put((name,text))
            finally:p.stdout.close();f.close()
        t=threading.Thread(target=read,daemon=True);t.start();threads.append(t);return p
    def tick():
        if (stop[0] or (job/'stop.request').exists()) and not (sensor and source_stopped):raise InterruptedError('Requested stop')
        if time.monotonic()-start>c['run']['timeout_s']:raise TimeoutError('Run timeout')
        for name,p in children:
            if name!='playback' and name not in expected_end and p.poll() is not None:raise RuntimeError(name+' exited: '+str(p.returncode))
            try:
                text=Path('/proc/%s/stat'%p.pid).read_text().split(') ',1)[1].split();cpu=(int(text[11])+int(text[12]))/os.sysconf('SC_CLK_TCK')
                fields={a:b.strip() for a,b in (line.split(':',1) for line in Path('/proc/%s/status'%p.pid).read_text().splitlines() if ':' in line)}
                pss=next((int(l.split()[1]) for l in Path('/proc/%s/smaps_rollup'%p.pid).read_text().splitlines() if l.startswith('Pss:')),0)
                prev=state['resource_samples'].setdefault(name,dict(cpu_s_lower_bound=0,rss_kib_peak_observed=0,pss_kib_peak_observed=0))
                prev.update(cpu_s_lower_bound=max(prev['cpu_s_lower_bound'],cpu),rss_kib_peak_observed=max(prev['rss_kib_peak_observed'],int(fields.get('VmRSS','0 kB').split()[0])),pss_kib_peak_observed=max(prev['pss_kib_peak_observed'],pss))
            except (OSError,ValueError,StopIteration):pass
        state['child_pids']={name:p.pid for name,p in children};save()
        if state.get('fatal_log'):raise RuntimeError(state['fatal_log'])
    def terminate(name,p):
        escalated=[]
        for sig,limit in [(signal.SIGINT,c['run']['shutdown_timeout_s']),(signal.SIGTERM,3),(signal.SIGKILL,3)]:
            if p.poll() is not None:break
            try:os.killpg(p.pid,sig)
            except ProcessLookupError:pass
            if sig!=signal.SIGINT:escalated.append(int(sig))
            try:p.wait(timeout=limit)
            except subprocess.TimeoutExpired:pass
        state['process_exits'][name]=p.poll()
        if escalated:state.setdefault('forced_cleanup',{})[name]=escalated
    def until(test,timeout,label):
        deadline=time.monotonic()+timeout
        while True:
            tick()
            try:
                if test():return
            except (OSError,xmlrpc.client.Error):pass
            if time.monotonic()>deadline:raise RuntimeError(label+' readiness timed out')
            time.sleep(.2)
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    code=1
    try:
        save();effective(c,job)
        if sensor:
            state['hardware_preflight']=check_hardware(c,install)
            state['record_only']=record_only
        else:
            report=subprocess.run([sys.executable,install/'runtime/bag_info.py',job/'project.json'],capture_output=True,text=True)
            if report.returncode:raise ValueError('Dataset check failed: '+report.stderr[-1500:])
            bag=json.loads(report.stdout);state['bag']=bag;atomic(job/'bag.json',bag)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        os.environ.update(ROS_MASTER_URI='http://127.0.0.1:'+str(port),ROS_IP='127.0.0.1',ROS_HOME=str(job/'ros-home'),ROS_LOG_DIR=str(job/'ros-logs'),ROSCONSOLE_STDOUT_LINE_BUFFERED='1')
        state['master_uri']=os.environ['ROS_MASTER_URI'];master=xmlrpc.client.ServerProxy(state['master_uri'],transport=Transport())
        event('master_start','Private master '+state['master_uri']);launch('master',['roscore','-p',port])
        until(lambda:master.getPid('/vins_platform')[0]==1,c['run']['startup_timeout_s'],'master')
        master.setParam('/vins_platform','/use_sim_time',not sensor)
        if not record_only:launch('vins',[install/'bin/vins_node',job/'vins.yaml'])
        inputs=[c['inputs']['camera']['topic'],c['inputs']['imu']['topic']]
        def subscribers():
            data=master.getSystemState('/vins_platform');subs={t:set(nodes) for t,nodes in data[2][1]}
            return all('/vins_estimator' in subs.get(t,set()) for t in inputs)
        if not record_only:until(subscribers,c['run']['startup_timeout_s'],'VINS subscriptions')
        cam=c['inputs']['camera'];monitor=c['monitor'].get('enabled',True) or sensor
        if monitor:
            launch('observer',[install/'bin/vins_observer','_image:='+inputs[0],'_imu:='+inputs[1],'_width:='+str(cam['width']),'_height:='+str(cam['height']),'_encoding:='+cam['encoding'],'_output:='+str(job/'observation.json')])
            until(lambda:(job/'observation.json').exists(),c['run']['startup_timeout_s'],'observer')
            until(lambda:all('/vins_observer' in dict(master.getSystemState('/vins_platform')[2][1]).get(t,[]) for t in inputs),c['run']['startup_timeout_s'],'observer subscriptions')
        if sensor:
            hw=camera_settings(c);im=c['inputs']['imu']['device'];raw=job/'raw';raw.mkdir()
            topics=inputs+[hw['raw_topic'],hw['metadata_topic'],im['raw_topic']]
            launch('recorder',['rosbag','record','--buffsize','256','--split','--size',c['recording']['split_mib'],'-O',raw/'capture',*topics,'__name:=vins_recorder'])
            until(lambda:all('/vins_recorder' in dict(master.getSystemState('/vins_platform')[2][1]).get(t,[]) for t in topics),c['run']['startup_timeout_s'],'recorder subscriptions')
            params=dict(serial=hw['serial'],topic=inputs[0],raw_topic=hw['raw_topic'],metadata_topic=hw['metadata_topic'],width=hw['width'],height=hw['height'],binning=hw['binning'],output_width=cam['width'],output_height=cam['height'],crop_x=hw['crop'][0],crop_y=hw['crop'][1],crop_width=hw['crop'][2],crop_height=hw['crop'][3],trigger=hw['trigger'],fps=hw['fps'],auto_max_us=hw['auto_max_us'],exposure_auto=hw['exposure_auto'],exposure_us=hw['exposure_us'])
            camera_process=launch('camera',[install/'bin/vins_camera',*['_'+k+':='+str(v) for k,v in params.items()]])
            # Wait for acquisition to be armed before starting the IMU reader.
            # The IMU's physical trigger generator is independent of UART reading.
            until(lambda:'Camera acquisition armed' in (job/'camera.log').read_text(),c['run']['startup_timeout_s'],'camera configuration')
            launch('imu',[install/'bin/vins_imu','_device:='+im['port'],'_baud:='+str(im['baud']),'_nominal_hz:='+str(im['nominal_hz']),'_topic:='+inputs[1],'_raw_topic:='+im['raw_topic']])
            state['phase']='capturing';event('capture_start','Recorder subscribed, camera armed for '+hw['trigger']+'; IMU reader started')
            playback=None
        else:
            args=['rosbag','play','--clock','--delay','1','--rate',c['dataset']['rate'],'--start',c['dataset']['start_s']]
            if c['dataset']['duration_s']:args+=['--duration',c['dataset']['duration_s']]
            args+=['--topics',*inputs,'--bags',*dataset_files(c)]
            playback=launch('playback',args);state['phase']='replaying';event('playback_start','VINS and observer subscribed')
        replay=time.monotonic();last_seq=None;seen=time.monotonic();lastpose=None;stable_since=time.monotonic()
        while True:
            now=time.monotonic()
            if sensor and state['phase']=='capturing' and (now-replay>=c['run']['duration_s'] or stop[0] or (job/'stop.request').exists()):
                source_stopped=True;state['stop_reason']='requested' if stop[0] or (job/'stop.request').exists() else 'duration'
                for source_name in ['camera','imu']:
                    for name,p in children:
                        if name==source_name:expected_end.add(name);terminate(name,p)
                    if source_name=='camera':time.sleep(.1)
                state['capture_wall_s']=time.monotonic()-replay;state['phase']='draining';drain=time.monotonic()
                event('source_ended','Hardware sources closed; waiting for trajectory tail and recorder flush')
            tick();now=time.monotonic()
            if monitor:
                obs=json.loads((job/'observation.json').read_text())
                if obs['seq']!=last_seq:last_seq=obs['seq'];seen=now
                if now-seen>max(3,c['monitor']['refresh_s']*3):raise RuntimeError('monitor_unavailable: observer snapshot stale')
                state['observation']=obs
                for name in ['image','imu','pose']:
                    row=obs[name]
                    if row['invalid'] or row['nonincreasing']:raise RuntimeError('invalid_input: '+name+' numeric/format/timestamp error')
                    if name!='pose' and state['phase'] in ['replaying','capturing']:
                        if not row['count'] and now-replay>c['monitor']['first_message_timeout_s']:raise RuntimeError('first_message_timeout: '+name)
                        if row['count'] and row['age_s']>c['monitor']['input_stall_s']:raise RuntimeError('input_stall: '+name)
            if not sensor and playback.poll() is not None and state['phase']=='replaying':
                if playback.returncode:raise RuntimeError('Playback exit '+str(playback.returncode))
                if monitor and any(not obs[t]['count'] for t in ['image','imu']):raise RuntimeError('source_ended_without_input: image/IMU not observed')
                state['playback_wall_s']=now-replay;state['phase']='draining';event('source_ended','Checking trajectory tail coverage; queue empty not directly instrumented');drain=now
            if state['phase']=='draining':
                if sensor and record_only:
                    if any(not obs[t]['count'] for t in ['image','imu']):raise RuntimeError('No image/IMU observed')
                    code=0;break
                trajectory=job/'vio.csv';size=trajectory.stat().st_size if trajectory.exists() else 0
                if size!=lastpose:lastpose=size;stable_since=now
                if now-drain>c['run']['drain_timeout_s']:raise TimeoutError('Trajectory drain timeout')
                if size and now-stable_since>=5:
                    rows=[l.rstrip(',').split(',') for l in trajectory.read_text().splitlines() if l.strip()]
                    stamps=[int(r[0]) for r in rows]
                    if not all(a<b for a,b in zip(stamps,stamps[1:])) or not all(math.isfinite(float(x)) for row in rows for x in row):raise ValueError('Invalid output trajectory')
                    tail=(obs['image']['stamp_ns'] if sensor else bag['topics'][inputs[0]]['last_ns'])-stamps[-1]
                    if sensor and not state.get('initialization_log_count'):raise ValueError('VINS initialization not observed')
                    if abs(tail)>max(100000000,2e9/cam['expected_hz']):raise ValueError('Output does not cover dataset tail: '+str(tail/1e9)+'s')
                    state.update(trajectory_poses=len(rows),last_pose_ns=stamps[-1],tail_s=tail/1e9,drain_s=now-drain,queue_empty_verified=False)
                    code=0;break
            save();time.sleep(.25)
    except InterruptedError as e:code=130;state['error']=str(e);event('cancelled',str(e))
    except TimeoutError as e:code=124;state['error']=str(e);event('timeout',str(e))
    except Exception as e:state['error']=str(e);event('failed',str(e))
    finally:
        state['phase']='stopping';save()
        for name,p in reversed(children):terminate(name,p)
        for t in threads:t.join(timeout=2)
        if code==0 and any(v!=0 for v in state['process_exits'].values()):code=1;state['error']='Nonzero shutdown exit'
        if sensor:
            try:
                from recording import inspect
                state['recording']=inspect(job,c);atomic(job/'recording.json',state['recording'])
            except Exception as e:
                state['recording_error']=str(e)
                if code==0:code=1;state['error']='Recording validation: '+str(e)
        usage=resource.getrusage(resource.RUSAGE_CHILDREN);state['child_cpu_s']=usage.ru_utime+usage.ru_stime-resource_start.ru_utime-resource_start.ru_stime
        state.update(phase='completed' if code==0 else 'cancelled' if code==130 else 'failed',exit_code=code)
        event(state['phase'],state.get('error','Recording and process exit checks passed' if record_only else 'Tail coverage and process exit checks passed'))
        logs=[p for p in job.iterdir() if p.name not in {'agent.log'} and (p.suffix=='.log' or p.name in {'ros-logs','ros-home'})]
        if c['results']['raw_logs']=='compressed' and logs:
            with tarfile.open(job/'logs.tar.gz','w:gz') as archive:
                for p in logs:archive.add(p,arcname=p.name)
            import shutil
            for p in logs:
                if p.is_dir():shutil.rmtree(p)
                else:p.unlink()
        atomic(job/'files.json',{str(p.relative_to(job)):digest(p) for p in sorted(job.rglob('*')) if p.is_file() and p.name not in {'state.json','files.json','agent.log','stop.request'} and (c['results']['raw_logs']!='none' or not(p.suffix=='.log' or {'ros-logs','ros-home'} & set(p.relative_to(job).parts)))})
        save();lock.close()
    return code
if __name__=='__main__':sys.exit(supervise(sys.argv[1],sys.argv[2]))
