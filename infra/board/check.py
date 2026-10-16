"""Select independent preflight checks; no ROS master, VINS or playback is started."""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys

from common import Invalid, bag_info, configuration, digest, directory, environment, install_root, readable, require


def architecture(root):
    machine = platform.machine().lower()
    require(machine in ('aarch64', 'arm64'), 'ARM64 board required; detected ' + machine)
    node = readable(root/'bin/vins_node')
    with node.open('rb') as stream:
        header = stream.read(20)
    require(len(header) == 20 and header[:6] == b'\x7fELF\x02\x01' and struct.unpack('<H', header[18:20])[0] == 183, 'Expected a little-endian ARM64 ELF: ' + str(node))
    release = json.loads(readable(root/'release.json').read_text())
    require(release.get('architecture') == 'aarch64' and release.get('ros') == 'ros1', 'Expected an aarch64 ROS 1 package: ' + str(root/'release.json'))
    return dict(machine=machine, node=str(node), version=release.get('version'))


def manifest(root):
    path = readable(root/'SHA256SUMS')
    entries = {}
    failures = []
    for line in path.read_text().splitlines():
        parts = line.split('  ', 1)
        require(len(parts) == 2 and len(parts[0]) == 64 and all(c in '0123456789abcdef' for c in parts[0]), 'Invalid SHA256SUMS entry: '+line)
        sha, name = parts
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts and name not in entries, 'Unsafe or duplicate manifest path: '+name)
        file = root/rel
        require(root in file.resolve().parents, 'Manifest path leaves install: '+str(file))
        entries[name] = sha
        try:
            if digest(readable(file)) != sha:
                failures.append('SHA256 differs: '+str(file))
        except OSError as error:
            failures.append('{}: {}'.format(file, error))
        except Invalid as error:
            failures.append(str(error))
    required = {'env.sh', 'bin/vins', 'bin/vins_node', 'release.json', 'config/euroc/euroc_stereo_imu_config.yaml'}
    require(required <= entries.keys(), 'Required files absent from manifest: '+', '.join(sorted(required-entries.keys())))
    for name in ['bin/vins', 'bin/vins_node', 'runtime/python38/bin/python3']:
        if name not in entries or not os.access(root/name, os.X_OK):
            failures.append('Missing executable or execute permission: '+str(root/name))
    require(not failures, '; '.join(failures))
    return dict(manifest=str(path), verified_files=len(entries))


def libraries(root):
    env = environment(root)
    failures, count, skipped = [], 0, 0
    for folder in [root/'bin', root/'runtime']:
        for path in sorted(folder.rglob('*')):
            if not path.is_file():
                continue
            with path.open('rb') as stream:
                header = stream.read(20)
                if len(header) < 20 or header[:4] != b'\x7fELF':
                    continue
                elf_type = struct.unpack('<H' if header[5] == 1 else '>H', header[16:18])[0]
                if elf_type not in (2, 3):
                    skipped += 1
                    continue
            count += 1
            result = subprocess.run(['ldd', str(path)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10)
            if 'not found' in result.stdout or (result.returncode and 'statically linked' not in result.stdout):
                failures.append('{}: {}'.format(path, result.stdout.strip()))
    require(count > 0, 'No ELF runtime files found under '+str(root))
    require(not failures, '\n'.join(failures))
    return dict(elf_files=count, skipped_non_loadable_elf_files=skipped, scope='ELF DT_NEEDED resolution; optional drivers/plugins are not loaded')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog='Examples: check --arc; check --arc --lib --sha --dir; check --config config/vio.yaml --bag data/input.bag --output runs/demo01')
    parser.add_argument('--mode', choices=['bag', 'sensor'], default='bag')
    parser.add_argument('--install', help='Install root; default selected package')
    for name, help_text in [('arc','ARM64 kernel, node ELF and package architecture'), ('lib','Resolve bundled ELF shared libraries'), ('sha','Verify required files and every SHA256SUMS entry'), ('dir','Probe output permission and free space')]:
        parser.add_argument('--'+name, action='store_true', help=help_text)
    parser.add_argument('--config', nargs='?', const='', metavar='YAML', help='Validate config/calibration; omit path for packaged EuRoC stereo example')
    parser.add_argument('--bag', type=Path, help='Check ROS 1 bag types/counts and header time overlap; uses --config or default')
    parser.add_argument('--timestamps', action='store_true', help='With --bag, scan every required-topic header for duplicate/reversed stamps')
    parser.add_argument('--output', type=Path, help='Directory to check; also overrides YAML output paths for a future run')
    parser.add_argument('--min-free-mb', type=float, default=512, help='Minimum available MiB for --dir (default 512)')
    parser.add_argument('--json', metavar='PATH', help='Save JSON report, or - for JSON-only stdout')
    args = parser.parse_args(argv)
    if args.mode == 'sensor':
        parser.error('sensor mode is reserved: device discovery, drivers, live topics and clock synchronization are not implemented; use --mode bag')
    if args.timestamps and not args.bag:
        parser.error('--timestamps requires --bag PATH')
    if not math.isfinite(args.min_free_mb) or args.min_free_mb < 0:
        parser.error('--min-free-mb must be finite and >= 0')
    if not any([args.arc, args.lib, args.sha, args.dir, args.config is not None, args.bag]):
        parser.print_help()
        return 2
    root = install_root(args.install)
    results = []
    def perform(name, function, path=None):
        if args.json != '-':
            print('[CHECK] {}: {}'.format(name,path or root),flush=True)
        try:
            details = function()
            result = dict(check=name, status='pass', details=details)
        except Exception as error:
            result = dict(check=name, status='fail', path=str(path or root), error='{}: {}'.format(type(error).__name__, error))
        results.append(result)
        if args.json != '-':
            details = result.get('details', {})
            if name == 'configuration' and details:
                details = {key:details[key] for key in ['path','topics','calibrations']}
            print('[{}] {}: {}'.format(result['status'].upper(), name, (result['error']+' ['+result['path']+']') if result.get('error') else json.dumps(details, ensure_ascii=False)), flush=True)
        return result
    if args.arc: perform('architecture', lambda: architecture(root))
    if args.lib: perform('libraries', lambda: libraries(root))
    if args.sha: perform('package_sha256', lambda: manifest(root))
    if args.dir: perform('output_directory', lambda: directory(args.output or Path.cwd()/'runs', args.min_free_mb))
    config = None
    if args.config is not None or args.bag:
        path = Path(args.config) if args.config else root/'config/euroc/euroc_stereo_imu_config.yaml'
        # --bag alone needs topic/calibration metadata, but does not validate an
        # unused YAML output location; --config explicitly checks that location.
        override = args.output or (Path.cwd()/'runs' if args.config is None else None)
        result = perform('configuration', lambda: configuration(path, root, override), path)
        if result['status'] == 'pass':
            config = result['details']
            if args.config is not None and args.output is None:
                for key in ['output_path','pose_graph_save_path']:
                    perform(key, lambda key=key: directory(config['values'][key], args.min_free_mb))
    if args.bag:
        if config is not None:
            perform('bag', lambda: bag_info(args.bag, config, root, args.timestamps), args.bag)
        else:
            results.append(dict(check='bag',status='fail',error='Cannot inspect topics because configuration failed'))
    report = dict(ok=all(r['status']=='pass' for r in results), mode=args.mode, install=str(root), results=results)
    text = json.dumps(report, indent=2, ensure_ascii=False)+'\n'
    if args.json == '-':
        print(text, end='')
    elif args.json:
        try:
            with Path(args.json).open('x') as stream: stream.write(text)
        except OSError as error:
            print('Cannot create report {}: {}'.format(args.json,error),file=sys.stderr)
            return 1
    if args.json != '-':
        print('CHECK {} ({} checks)'.format('PASSED' if report['ok'] else 'FAILED',len(results)))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
