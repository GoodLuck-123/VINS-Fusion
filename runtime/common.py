"""Shared configuration and artifact rules (also runs in the private Python 3.8)."""
import hashlib,json,math,os,re,shutil
from pathlib import Path

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def atomic(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(str(tmp),str(p))

def load(path):
    import yaml
    class Strict(yaml.SafeLoader):pass
    def mapping(loader,node,deep=False):
        out={}
        for k,v in node.value:
            key=loader.construct_object(k,deep=deep)
            if key in out:raise ValueError('Duplicate configuration key: '+str(key))
            out[key]=loader.construct_object(v,deep=deep)
        return out
    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    path=Path(path).expanduser().resolve()
    if not path.is_file():raise ValueError('配置不存在：{}；先 cp project.example.yaml {}'.format(path,path.name))
    c=yaml.load(path.read_text(),Loader=Strict)
    try:
        if c['schema_version']!=1 or c['run']['mode'] not in ['replay','sensor']:raise ValueError('Expected schema 1 and run.mode replay/sensor')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',c['run']['name']):raise ValueError('run.name: use letters/digits/._-, 1..64 characters')
        for d in ['run','dataset','monitor','inputs','vins','board','paths','build','results']:
            if not isinstance(c[d],dict):raise ValueError(d+' must be a mapping')
        def num(value,key,low=0):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=low:raise ValueError(key+' must be finite and > '+str(low))
        for key in ['timeout_s','startup_timeout_s','drain_timeout_s','shutdown_timeout_s','min_free_gib']:num(c['run'][key],'run.'+key)
        if 'enabled' in c['monitor'] and type(c['monitor']['enabled']) is not bool:raise ValueError('monitor.enabled must be boolean')
        for key in ['refresh_s','first_message_timeout_s','input_stall_s','repeat_notice_s']:num(c['monitor'][key],'monitor.'+key)
        num(c['dataset']['rate'],'dataset.rate');num(c['build']['jobs'],'build.jobs')
        if type(c['build']['jobs']) is not int:raise ValueError('build.jobs must be integer')
        if not 0<c['dataset']['rate']<=1:raise ValueError('dataset.rate must be in (0,1]')
        if isinstance(c['dataset']['start_s'],bool) or not isinstance(c['dataset']['start_s'],(int,float)) or not math.isfinite(c['dataset']['start_s']) or c['dataset']['start_s']<0:raise ValueError('dataset.start_s must be >= 0')
        if c['dataset']['duration_s'] is not None:num(c['dataset']['duration_s'],'dataset.duration_s')
        camera=c['inputs']['camera'];imu=c['inputs']['imu']
        if imu['enabled'] is not True:raise ValueError('v0.1 requires monocular + IMU')
        if (imu['acceleration_unit'],imu['angular_velocity_unit'])!=('m/s^2','rad/s'):raise ValueError('IMU units must be m/s^2 and rad/s')
        for key in ['width','height']:
            if type(camera[key]) is not int or camera[key]<1:raise ValueError('inputs.camera.'+key+' must be positive integer')
        if camera['encoding'] not in ['mono8','8UC1']:raise ValueError('v0.1 supports mono8/8UC1 images')
        for stream in [camera,imu]:
            if not re.fullmatch(r'/[A-Za-z][A-Za-z0-9_/]*',stream['topic']):raise ValueError('Invalid input topic: '+str(stream['topic']))
            num(stream['expected_hz'],'inputs.*.expected_hz')
        if camera['topic']==imu['topic']:raise ValueError('Input topics must differ')
        if c['run']['mode']=='sensor':
            num(c['run']['duration_s'],'run.duration_s')
            if c['run']['duration_s']>=c['run']['timeout_s']:raise ValueError('run.duration_s must be less than run.timeout_s')
            hw=camera_settings(c);serial=imu['device'];rec=c['recording']
            if not re.fullmatch(r'[0-9]+',str(hw['serial'])):raise ValueError('Camera serial must be numeric')
            for key in ['binning','width','height']:
                if type(hw[key]) is not int or hw[key]<1:raise ValueError('camera.device.'+key+' must be a positive integer')
            crop=hw['crop']
            if len(crop)!=4 or any(type(x) is not int for x in crop) or min(crop[:2])<0 or min(crop[2:])<1 or crop[0]+crop[2]>hw['width'] or crop[1]+crop[3]>hw['height']:raise ValueError('Camera crop outside raw frame')
            if hw['trigger'] not in ['hardware','software','continuous']:raise ValueError('camera.device.trigger must be hardware/software/continuous')
            if hw['exposure_auto'] not in ['Off','Continuous']:raise ValueError('camera.device.exposure_auto must be Off/Continuous')
            num(hw['exposure_us'],'camera.device.exposure.time_us');num(hw['auto_max_us'],'camera.device.exposure.auto_max_us');num(hw['fps'],'camera.device.fps')
            if not str(serial['port']).startswith('/dev/') or serial['baud']!=115200:raise ValueError('GNW needs a /dev/ path and verified 115200 baud')
            num(serial['nominal_hz'],'imu.device.nominal_hz')
            if type(rec['split_mib']) is not int or rec['split_mib']<32:raise ValueError('recording.split_mib must be integer >= 32')
            topics=[camera['topic'],imu['topic'],hw['raw_topic'],hw['metadata_topic'],serial['raw_topic']]
            if len(set(topics))!=5 or any(not re.fullmatch(r'/[A-Za-z][A-Za-z0-9_/]*',t) for t in topics):raise ValueError('Hardware topics must be valid and distinct')
            if type(rec['enabled']) is not bool or not rec['enabled']:raise ValueError('v0.2 sensor tasks require recording.enabled=true')
            if camera['calibration']['verified_for']=='euroc-cam0':raise ValueError('EuRoC calibration cannot be used for physical hardware')
        if c['results']['raw_data'] not in ['always','on_request']:raise ValueError('results.raw_data must be always/on_request')
        v=c['vins']
        for k in ['multiple_thread','show_track','flow_back','estimate_td']:
            if type(v[k]) is not int or v[k] not in [0,1]:raise ValueError('vins.'+k+' must be 0 or 1')
        for k in ['max_cnt','min_dist','max_num_iterations']:
            if type(v[k]) is not int or v[k]<1:raise ValueError('vins.'+k+' must be positive integer')
        for k in ['F_threshold','max_solver_time','keyframe_parallax','acc_n','gyr_n','acc_w','gyr_w','g_norm']:num(v[k],'vins.'+k)
        if not math.isfinite(v['td']) or v['estimate_extrinsic'] not in [0,1,2]:raise ValueError('Invalid VINS time/extrinsic setting')
        t=v['body_T_cam0']
        if len(t)!=4 or any(len(r)!=4 for r in t) or not all(math.isfinite(x) for r in t for x in r):raise ValueError('body_T_cam0 must be finite 4x4')
        if any(abs(a-b)>1e-6 for a,b in zip(t[3],[0,0,0,1])):raise ValueError('Invalid homogeneous transform last row')
        r=[row[:3] for row in t[:3]]
        if any(abs(sum(r[k][i]*r[k][j] for k in range(3))-(i==j))>1e-3 for i in range(3) for j in range(3)):raise ValueError('body_T_cam0 rotation is not orthonormal')
        det=sum(r[0][i]*(r[1][(i+1)%3]*r[2][(i+2)%3]-r[1][(i+2)%3]*r[2][(i+1)%3]) for i in range(3))
        if abs(det-1)>1e-3:raise ValueError('body_T_cam0 rotation determinant must be +1')
        cal=camera['calibration'];fields={'MEI':['gamma1','gamma2','u0','v0'],'PINHOLE':['fx','fy','cx','cy']}
        if cal['model'] not in fields:raise ValueError('v0.1 camera model must be MEI/PINHOLE')
        for key in fields[cal['model']]:
            if not math.isfinite(cal['projection'][key]):raise ValueError('Invalid camera projection: '+key)
        for key in ['k1','k2','p1','p2']:
            if not math.isfinite(cal['distortion'][key]):raise ValueError('Invalid camera distortion: '+key)
        if cal['model']=='MEI' and not math.isfinite(cal['xi']):raise ValueError('Invalid MEI xi')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+',c['board']['target']):raise ValueError('board.target must be user@host')
        if type(c['board']['ssh_port']) is not int or not 1<=c['board']['ssh_port']<=65535:raise ValueError('Invalid board.ssh_port')
        if c['results']['raw_logs'] not in ['compressed','none']:raise ValueError('results.raw_logs must be compressed/none')
    except KeyError as e:raise ValueError('配置缺少必填键：'+str(e)) from e
    except (TypeError,AttributeError) as e:raise ValueError('配置字段类型错误：'+str(e)) from e
    c['_config']=str(path)
    root=Path(__file__).resolve().parent.parent
    # Build/cache/release layout is an engineering contract, not silently ignored overrides.
    if (root/'cli.py').is_file():
        for key in ['cache','build','releases']:
            if (path.parent/Path(c['paths'][key]).expanduser()).resolve()!=root/key:raise ValueError('paths.'+key+' must point to '+str(root/key))
    for key,value in c['paths'].items():c['paths'][key]=str((path.parent/Path(value).expanduser()).resolve())
    for key in ['bag','ground_truth']:
        if c['dataset'][key]:c['dataset'][key]=str((path.parent/Path(c['dataset'][key]).expanduser()).resolve())
    return c

def effective(c,job):
    import yaml
    cam=c['inputs']['camera'];cal=cam['calibration'];v=dict(c['vins']);t=v.pop('body_T_cam0')
    v.update(imu=1,num_of_cam=1,image0_topic=cam['topic'],image1_topic='',imu_topic=c['inputs']['imu']['topic'],image_width=cam['width'],image_height=cam['height'],cam0_calib='camera.yaml',output_path=str(job))
    text=yaml.safe_dump(v,sort_keys=False)+'body_T_cam0: !!opencv-matrix\n  rows: 4\n  cols: 4\n  dt: d\n  data: '+str([x for row in t for x in row])+'\n'
    (job/'vins.yaml').write_text('%YAML:1.0\n---\n'+text)
    model=dict(model_type=cal['model'],camera_name='cam0',image_width=cam['width'],image_height=cam['height'],distortion_parameters=cal['distortion'],projection_parameters=cal['projection'])
    if cal['model']=='MEI':model['mirror_parameters']={'xi':cal['xi']}
    (job/'camera.yaml').write_text('%YAML:1.0\n---\n'+yaml.safe_dump(model,sort_keys=False))

def verify_install(root):
    import platform,subprocess
    root=Path(root);meta=json.loads((root/'release.json').read_text())
    if meta['architecture']!=platform.machine():raise ValueError('Package architecture mismatch: '+meta['architecture'])
    for name,value in json.loads((root/'files.json').read_text()).items():
        p=root/name
        if not p.is_file() or digest(p)!=value:raise ValueError('Package file missing/corrupt: '+str(p))
    required=[root/'bin/vins_node',root/'bin/vins_observer',root/'python/bin/python3',root/'ros/lib/rosout/rosout',root/'ros/lib/rosbag/play']
    if meta.get('sensors'):required += [root/'bin/vins_camera',root/'bin/vins_imu',root/'ros/lib/rosbag/record',root/'spinnaker/lib/flir-gentl/FLIR_GenTL.cti']
    for p in required:
        if not p.is_file() or (p.suffix!='.cti' and not os.access(p,os.X_OK)):raise ValueError('Required executable missing: '+str(p))
        r=subprocess.run(['ldd',str(p)],capture_output=True,text=True)
        if r.returncode or 'not found' in r.stdout:raise ValueError('Shared library failure: '+str(p)+'\n'+r.stdout+r.stderr)
    return meta


def check_hardware(c,root):
    """No device mutation: access and package checks; acquisition occurs in the task."""
    import subprocess
    root=Path(root);verify_install(root)
    if not (root/'bin/vins_camera').is_file():raise ValueError('运行包不含 ARM64 相机/IMU 适配器；重新 build/deploy')
    port=c['inputs']['imu']['device']['port']
    if not os.access(port,os.R_OK|os.W_OK):raise ValueError('IMU 设备不存在或权限不足：'+port)
    # Detect a busy serial device before starting any task-owned process.
    result=subprocess.run(['fuser',port],capture_output=True,text=True)
    if result.returncode==0:raise ValueError('IMU 串口已被占用：'+port+' PID '+result.stdout.strip())
    free=shutil.disk_usage(c['_workspace']).free
    cam=c['inputs']['camera'];estimated=(camera_settings(c)['width']*camera_settings(c)['height']+cam['width']*cam['height'])*cam['expected_hz']*c['run']['duration_s']*1.15
    if free<estimated+c['run']['min_free_gib']*2**30:raise ValueError('录包空间不足：估计 {:.2f} GiB，另需保留 {:.2f} GiB'.format(estimated/2**30,c['run']['min_free_gib']))
    return dict(serial=port,free_bytes=free,estimated_record_bytes=int(estimated),camera_serial=str(camera_settings(c)['serial']),camera_device_access='checked at acquisition')


def camera_settings(c):
    """Only experiment-facing SDK controls are user configurable; remaining policy is fixed."""
    device=c['inputs']['camera']['device'];binning=device['binning']
    if type(binning) is not int or binning not in [1,2]:raise ValueError('camera.device.binning must be 1 or 2')
    if device['exposure']['mode'] not in ['auto','manual']:raise ValueError('camera.device.exposure.mode must be auto/manual')
    settings=dict(serial=str(device['serial']),binning=binning,width=2048//binning,height=1536//binning,crop=device['crop'],trigger=device['trigger'],fps=device['fps'],exposure_auto='Continuous' if device['exposure']['mode']=='auto' else 'Off',exposure_us=device['exposure']['time_us'],auto_max_us=device['exposure']['auto_max_us'],raw_topic='/usb_camera/raw/image_raw',metadata_topic='/usb_camera/frame_metadata')
    return settings


def dataset_files(c):
    p=Path(c['dataset']['bag'])
    paths=sorted(p.glob('*.bag')) if p.is_dir() else [p]
    if not paths or any(not x.is_file() for x in paths):raise ValueError('数据集不存在或目录没有 .bag：'+str(p))
    if p.is_dir() and list(p.glob('*.active')):raise ValueError('数据目录含未正常关闭的 .active bag：'+str(p))
    return paths
