"""Standalone board bag runner. It does not call the host deployment or run tools."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import xmlrpc.client

from common import Invalid, bag_info, configuration, digest, directory, environment, install_root, prepare_config, readable, require


class Cancelled(Exception):
    pass


class Transport(xmlrpc.client.Transport):
    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = 1
        return connection


class Processes:
    def __init__(self, output, env):
        self.output, self.env, self.children, self.readers = output, env, [], []

    def launch(self, name, command):
        log = (self.output/(name+'.log')).open('w')
        try:
            child = subprocess.Popen(command, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except Exception:
            log.close()
            raise
        self.children.append((name,child))
        def relay():
            try:
                for line in iter(child.stdout.readline, b''):
                    text = line.decode(errors='replace')
                    log.write(text);log.flush()
                    print('[{}] {}'.format(name,text.rstrip()),flush=True)
            finally:
                child.stdout.close();log.close()
        reader = threading.Thread(target=relay,daemon=True)
        reader.start();self.readers.append(reader)
        return child

    def alive(self):
        for name, child in self.children:
            if child.poll() is not None:
                raise Invalid('{} exited unexpectedly with {}; see {}'.format(name,child.returncode,self.output/(name+'.log')))

    def stop(self):
        exits = {}
        for name, child in reversed(self.children):
            if child.poll() is None:
                for sig, timeout in [(signal.SIGINT,10),(signal.SIGTERM,3),(signal.SIGKILL,3)]:
                    try:os.killpg(child.pid,sig)
                    except ProcessLookupError:pass
                    try:
                        child.wait(timeout=timeout);break
                    except subprocess.TimeoutExpired:continue
            exits[name] = child.poll()
        for reader in self.readers:reader.join(timeout=2)
        return exits


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['bag','sensor'],default='bag')
    parser.add_argument('--bag',type=Path,help='ROS 1 bag; required in bag mode')
    parser.add_argument('--config',type=Path,help='Default: packaged EuRoC stereo + IMU configuration')
    parser.add_argument('--name',default='run01',help='Readable experiment name under ./runs/ (default run01)')
    parser.add_argument('--output',type=Path,help='Override with a new explicit board result directory')
    parser.add_argument('--install',help='Install root; default selected package')
    parser.add_argument('--rate',type=float,default=1.0,help='Playback speed in (0,1]')
    parser.add_argument('--port',type=int,help='Private loopback ROS master port; default automatically available port')
    parser.add_argument('--timeout',type=float,help='Overall deadline in seconds; default bag/rate + 240')
    parser.add_argument('--min-free-mb',type=float,default=512)
    args = parser.parse_args(argv)
    if args.mode == 'sensor':parser.error('sensor mode is reserved; drivers, live topic readiness and synchronization are not implemented')
    if not args.bag:parser.error('bag mode requires --bag PATH')
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',args.name):parser.error('Invalid --name; use 1..80 letters/digits/._- starting with a letter or digit')
    if not math.isfinite(args.rate) or not 0 < args.rate <= 1:parser.error('--rate must be in (0,1]')
    if args.port is not None and not 1024 <= args.port <= 65535:parser.error('--port must be 1024..65535')
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout<=0):parser.error('--timeout must be finite and > 0')
    if not math.isfinite(args.min_free_mb) or args.min_free_mb<0:parser.error('--min-free-mb must be finite and >= 0')
    root = install_root(args.install)
    output = (args.output or Path.cwd()/'runs'/args.name).expanduser().absolute()
    children = None
    metadata = dict(status='failed',mode='bag',output=str(output),stages=[],process_exits={})
    cancelled = [False]
    def request_stop(signum, frame):
        cancelled[0] = True
    old_handlers = {sig:signal.signal(sig,request_stop) for sig in (signal.SIGINT,signal.SIGTERM)}
    started = time.monotonic()
    lock = None
    created = False
    code = 1
    def stage(name, message):
        metadata['stages'].append(dict(code=name,elapsed_s=time.monotonic()-started,message=message))
        print('[{}] {}'.format(name,message),flush=True)
    def pending():
        if cancelled[0]:raise Cancelled('User requested stop')
        if time.monotonic()-started > deadline:raise TimeoutError('Run deadline exceeded')
    try:
        require(not output.exists() and not output.is_symlink(),'Output already exists; choose a new --name/--output: '+str(output))
        directory(output,args.min_free_mb)
        config = configuration(args.config or root/'config/euroc/euroc_stereo_imu_config.yaml',root,output)
        bag = bag_info(args.bag,config,root)
        metadata.update(bag=bag,source_config=config['path'],package=json.loads(readable(root/'release.json').read_text()),binary_sha256=digest(readable(root/'bin/vins_node')))
        deadline = args.timeout if args.timeout is not None else bag['duration_s']/args.rate+240
        pending()
        # Serialize users of this project. flock is released even on a crash;
        # keep the inode rather than unlinking another runner's lock file.
        lock = (Path.cwd()/'.vins-run.lock').open('a+')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Invalid('Another run holds the project lock: '+str(Path.cwd()/'.vins-run.lock'))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',args.port or 0));port=probe.getsockname()[1]
        output.mkdir(parents=True,exist_ok=False);created=True
        effective = prepare_config(config,output)
        env = environment(root)
        env.update(ROS_MASTER_URI='http://127.0.0.1:'+str(port),ROS_IP='127.0.0.1',ROS_HOME=str(output/'ros-home'),ROS_LOG_DIR=str(output/'ros-logs'),ROSCONSOLE_STDOUT_LINE_BUFFERED='1')
        metadata.update(rate=args.rate,config=str(effective),config_sha256=digest(effective),master_uri=env['ROS_MASTER_URI'])
        children = Processes(output,env)
        stage('MASTER_STARTING',env['ROS_MASTER_URI'])
        children.launch('roscore',['roscore','-p',str(port)])
        master=xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'],transport=Transport())
        ready_deadline=time.monotonic()+30
        while True:
            pending();children.alive()
            try:
                if master.getPid('/vins_run')[0]==1:break
            except (OSError,xmlrpc.client.Error):pass
            require(time.monotonic()<ready_deadline,'ROS master readiness timed out; see '+str(output/'roscore.log'))
            time.sleep(.2)
        require(master.setParam('/vins_run','/use_sim_time',True)[0]==1,'Cannot enable /use_sim_time')
        stage('VINS_STARTING',str(effective))
        children.launch('vins',[str(root/'bin/vins_node'),str(effective)])
        ready_deadline=time.monotonic()+30
        while True:
            pending();children.alive()
            state=master.getSystemState('/vins_run')
            subscriptions={topic for topic,nodes in state[2][1] if '/vins_estimator' in nodes} if state[0]==1 else set()
            if set(config['topics'])<=subscriptions:break
            require(time.monotonic()<ready_deadline,'VINS subscription readiness timed out; expected '+', '.join(config['topics']))
            time.sleep(.2)
        stage('PLAYBACK_STARTED','Subscriptions ready; '+str(args.bag))
        playback=children.launch('playback',['rosbag','play','--clock','--rate',str(args.rate),'--delay','1','--topics',*config['topics'],'--bags',bag['path']])
        replay_started=time.monotonic()
        while playback.poll() is None:
            pending()
            for name,child in children.children[:-1]:
                require(child.poll() is None,'{} exited during playback: {}'.format(name,child.returncode))
            time.sleep(.2)
        require(playback.returncode==0,'Playback failed: '+str(playback.returncode))
        metadata['playback_wall_s']=time.monotonic()-replay_started
        stage('DATA_ENDED','Waiting for trajectory output to settle; this is not a queue-empty proof')
        drain_started=time.monotonic();stable=0;previous=-1
        trajectory=output/'vio.csv'
        while stable<5:
            pending()
            for name,child in children.children[:-1]:
                require(child.poll() is None,'{} exited while draining: {}'.format(name,child.returncode))
            size=trajectory.stat().st_size if trajectory.exists() else 0
            stable=stable+1 if size==previous else 0;previous=size
            require(time.monotonic()-drain_started<60,'Trajectory did not settle within 60 seconds')
            time.sleep(1)
        rows=[row for row in readable(trajectory).read_text().splitlines() if row.strip()]
        require(rows,'Trajectory is empty: '+str(trajectory))
        stamps=[int(row.split(',')[0]) for row in rows]
        require(all(a<b for a,b in zip(stamps,stamps[1:])),'Trajectory timestamps are not strictly increasing')
        require(all(math.isfinite(float(v)) for row in rows for v in row.rstrip(',').split(',')),'Trajectory contains non-finite values')
        primary=bag['topics'][config['values']['image0_topic']]
        period=(primary['last_ns']-primary['first_ns'])/max(1,primary['count']-1)
        require(abs(primary['last_ns']-stamps[-1])<=max(100000000,2*period),'Trajectory does not cover the final input frames')
        metadata.update(trajectory_poses=len(rows),first_timestamp_ns=stamps[0],last_timestamp_ns=stamps[-1],drain_s=time.monotonic()-drain_started)
        metadata['status']='completed';code=0
    except Cancelled as error:
        metadata.update(status='cancelled',error=str(error));code=130
        stage('CANCELLED',str(error))
    except TimeoutError as error:
        metadata.update(status='failed',error=str(error));code=124
        stage('TIMEOUT',str(error))
    except Exception as error:
        metadata.update(status='cancelled' if cancelled[0] else 'failed',error='{}: {}'.format(type(error).__name__,error));code=130 if cancelled[0] else 1
        stage('FAILED',metadata['error'])
    finally:
        if children:
            stage('STOPPING','Stopping only the processes owned by this run')
            metadata['process_exits']=children.stop()
            if metadata['status']=='completed' and any(value!=0 for value in metadata['process_exits'].values()):
                metadata.update(status='failed',error='Nonzero child exit at shutdown: '+json.dumps(metadata['process_exits']))
                if metadata['process_exits'].get('vins')==-6:
                    metadata['known_issue']='Original v0.1 VINS sync-thread shutdown abort; data completion does not mean clean shutdown'
                code=1
        if lock:lock.close()
        if cancelled[0] and metadata['status']=='completed':
            metadata['status']='cancelled';code=130
        stage('RUN_'+metadata['status'].upper(),str(output))
        metadata['elapsed_s']=time.monotonic()-started
        if created:
            temporary=output/'run.json.tmp';temporary.write_text(json.dumps(metadata,indent=2)+'\n');temporary.replace(output/'run.json')
        for sig,handler in old_handlers.items():signal.signal(sig,handler)
    return code


if __name__ == '__main__':
    sys.exit(main())
