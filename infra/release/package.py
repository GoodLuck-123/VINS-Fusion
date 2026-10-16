"""Repack an accepted ARM runtime into a relocatable, user-facing install archive."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_verified(source, manifest_path, destination, mappings, lineage):
    manifest = json.loads(manifest_path.read_text())
    if sha(source / 'files.json') != sha(manifest_path):
        raise RuntimeError('Runtime manifest is not the accepted manifest')
    for name, expected in manifest.items():
        path = source / name
        if sha(path) != expected:
            raise RuntimeError('Accepted file changed: ' + str(path))
        for old, new in mappings:
            if name.startswith(old):
                relative = new + name[len(old):]
                target = destination / relative
                if target.exists():
                    raise RuntimeError('Package collision: ' + relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                lineage.append(dict(source=str(path), destination=relative, sha256=expected))
                break


def apply_ros1_build(root, lineage, build_path, validation_path):
    """Replace the linked node/library pair only after build and board validation."""
    build = json.loads(build_path.read_text())
    validation = json.loads(validation_path.read_text())
    if build.get('status') != 'pass' or validation.get('status') != 'pass':
        raise RuntimeError('Both build and board validation must pass')
    if not validation.get('accuracy_accepted') or not validation.get('edge_tests_passed'):
        raise RuntimeError('Complete replay/accuracy and shutdown edge validation required')
    core = ['camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion', 'config']
    commit = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', build['core_reference']+'^{commit}'], text=True).strip()
    if subprocess.check_output(['git', '-C', str(REPO), 'diff', commit, '--', *core]):
        raise RuntimeError('Current core differs from the verified build source')
    node = next(Path(name) for name in build['binaries'] if name.endswith('/vins/vins_node'))
    library = node.parents[1] / 'libvins_lib.so'
    needed = runpy.run_path(str(REPO / 'infra/rk3588/scripts/bundle_elf.py'))['needed']
    replacements = [('bin/vins_node', node, 'candidate_binary_sha256'),
                    ('runtime/lib/libvins_lib.so', library, 'candidate_library_sha256')]
    for relative, source, key in replacements:
        digest = sha(source)
        if build['elf_files'][str(source.resolve())]['sha256'] != digest or validation[key] != digest:
            raise RuntimeError('Validated build/board artifact mismatch: '+str(source))
        if sorted(needed(root/relative)) != sorted(needed(source)):
            raise RuntimeError('Dependency change needs a rebuilt full runtime: '+relative)
        shutil.copy2(source, root/relative)
        item = next(item for item in lineage if item['destination']==relative)
        item.update(base_sha256=item['sha256'], source=str(source), sha256=digest)
    source_path = root/'share/provenance/build_source.json'
    source = json.loads(source_path.read_text())
    source.update(base_source_commit=source['source_commit'], base_build_source_sha256=sha(source_path),
                  source_commit=commit, source_modified=False, shutdown_clean=True,
                  core_config_blobs=subprocess.check_output(['git', '-C', str(REPO), 'ls-tree', '-r', commit, '--', *core], text=True).splitlines(),
                  build_validation_sha256=sha(build_path), board_validation_sha256=sha(validation_path))
    source_path.write_text(json.dumps(source, indent=2)+'\n')
    item = next(item for item in lineage if item['destination']=='share/provenance/build_source.json')
    item.update(base_sha256=item['sha256'], source='generated from verified build and board validation', sha256=sha(source_path))
    for path, name in [(build_path,'build_validation.json'), (validation_path,'board_validation.json')]:
        shutil.copy2(path, root/'share/provenance'/name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ros', choices=['ros1', 'ros2'], required=True)
    parser.add_argument('--version', default='v0.1')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--addon', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New release directory, outside the Git checkout')
    parser.add_argument('--ros1-build-validation', type=Path, help='Verified cross build for the node and libvins_lib pair')
    parser.add_argument('--ros1-runtime-validation', type=Path, help='Accepted shutdown edges and complete A/B accuracy report')
    args = parser.parse_args()
    if bool(args.ros1_build_validation) != bool(args.ros1_runtime_validation) or (args.ros1_build_validation and args.ros != 'ros1'):
        parser.error('ROS1 build/runtime validations must be supplied together for ROS1')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+(?:\.[0-9]+)?', args.version):
        parser.error('Use a version such as v0.1 or v0.1.1')
    output = args.output.resolve()
    if output == REPO or REPO in output.parents:
        parser.error('Release output belongs outside the Git checkout')
    output.mkdir(parents=True, exist_ok=False)
    root = output / 'install'
    root.mkdir()
    reference = REPO / 'infra/rk3588/reference'
    lineage = []
    common = [('.infra/runtime/', 'runtime/'), ('VINS-Fusion/config/', 'config/'),
              ('build_source.json', 'share/provenance/build_source.json')]
    if args.ros == 'ros1':
        manifest = reference / 'ros1_runtime_20261014/payload_files.json'
        mappings = [('.infra/vins_ws/devel/lib/vins/vins_node', 'bin/vins_node'),
                    ('.infra/ros1/', 'runtime/ros/'), ('.infra/python38/', 'runtime/python38/'), *common]
    else:
        manifest = reference / 'runtime_20261014/payload_files.json'
        mappings = [('.infra/ros2_ws/install/', 'app/'), ('.infra/ros2/', 'runtime/ros/'),
                    ('cyclonedds.xml', 'share/cyclonedds.xml'), *common]
    copy_verified(args.runtime.resolve(), manifest, root, mappings, lineage)
    if args.ros == 'ros2':
        if not args.addon:
            parser.error('ROS 2 complete package requires --addon (accepted Fast DDS runtime)')
        copy_verified(args.addon.resolve(), reference / 'fastrtps_20261014/addon_files.json', root,
                      [('ros/', 'runtime/fastrtps/')], lineage)
    if args.ros == 'ros1' and not args.ros1_build_validation:
        base = json.loads((root/'share/provenance/build_source.json').read_text())
        if subprocess.check_output(['git', '-C', str(REPO), 'diff', base['source_commit'], '--', 'camera_models','vins_estimator','loop_fusion','global_fusion','config']):
            raise RuntimeError('Core changed: supply verified rebuilt node/library pair; do not relabel the old runtime')
    if args.ros1_build_validation:
        apply_ros1_build(root, lineage, args.ros1_build_validation.resolve(), args.ros1_runtime_validation.resolve())
    for name, target in [('env.sh', 'env.sh'), ('vins', 'bin/vins'), ('check.py', 'scripts/check.py')]:
        dest = root / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / name, dest)
        if name != 'check.py':
            dest.chmod(0o755)
    # Reuse the accepted lifecycle probes, relocating paths only. Reject a
    # changed template rather than silently producing an untested probe.
    if args.ros == 'ros1':
        probe = (REPO / 'infra/rk3588/scripts/ros1_runtime_smoke.sh').read_text()
        replacements = {'/runtime_env.sh': '/env.sh', "root/'.infra/vins_ws/devel/lib/vins/vins_node'": "root/'bin/vins_node'",
                        "root/'VINS-Fusion/config/euroc'": "root/'config/euroc'",
                        '.infra/runtime/lib/libopencv_core.so.4.2': 'runtime/lib/libopencv_core.so.4.2'}
        probe_path = root / 'scripts/smoke.sh'
    else:
        probe = (REPO / 'infra/rk3588/scripts/ros2_runtime_smoke.py').read_text()
        replacements = {'ROOT = Path(__file__).resolve().parent': 'ROOT = Path(os.environ["VINS_INSTALL_ROOT"])',
                        "ROOT / 'VINS-Fusion/infra/desktop/scripts'": "ROOT / 'scripts/reference'",
                        "ROOT / 'VINS-Fusion/config/euroc": "ROOT / 'config/euroc",
                        "ROOT / '.infra/ros2_ws/install/lib/vins/vins_node'": "ROOT / 'app/lib/vins/vins_node'",
                        "ROOT / 'build_source.json'": "ROOT / 'share/provenance/build_source.json'"}
        probe_path = root / 'scripts/smoke.py'
        helpers = root / 'scripts/reference'
        helpers.mkdir()
        shutil.copy2(REPO / 'infra/desktop/scripts/component_tools.py', helpers / 'component_tools.py')
    for old, new in replacements.items():
        if old not in probe:
            raise RuntimeError('Lifecycle probe template changed: ' + old)
        probe = probe.replace(old, new)
    # Both probes already validate a JSON manifest; derive it from the public
    # SHA256SUMS so there is only one authoritative package file list.
    old = "json.loads((root/'files.json').read_text())" if args.ros == 'ros1' else "json.loads((ROOT / 'files.json').read_text())"
    new = "{line.split('  ',1)[1]: line.split('  ',1)[0] for line in (ROOT / 'SHA256SUMS').read_text().splitlines()}"
    if args.ros == 'ros1':
        new = new.replace('ROOT /', 'root /')
        probe = probe.replace("root/'build_source.json'", "root/'share/provenance/build_source.json'")
    if old not in probe:
        raise RuntimeError('Lifecycle manifest template changed')
    probe_path.write_text(probe.replace(old, new))
    if args.ros == 'ros1':
        scripts = root / 'scripts/reference'
        scripts.mkdir()
        for name in ['run_euroc_baseline.py', 'process_metrics.py']:
            shutil.copy2(REPO / 'infra/desktop/scripts' / name, scripts / name)
        # Only path discovery changes in the packaged reference runner.
        (scripts / 'workspace_paths.py').write_text(
            'from pathlib import Path\nREPO_ROOT = Path(__file__).resolve().parents[2]\nWORKSPACE_ROOT = REPO_ROOT\n')
    if args.ros == 'ros1':
        runpy.run_path(str(REPO / 'infra/board/install.py'))['install'](root)
    metadata = dict(version=args.version, ros=args.ros, architecture='aarch64',
                    target='RK3588 Ubuntu 22.04', default_role='deployment' if args.ros == 'ros1' else 'research',
                    packaging_commit=subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
                    source=json.loads((root / 'share/provenance/build_source.json').read_text()),
                    accepted_manifest_sha256=sha(manifest),
                    known_limitations=['ROS1 original sync-thread shutdown abort retained'] if args.ros == 'ros1' and not args.ros1_build_validation else [])
    (root / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (root / 'share/provenance/file_lineage.json').write_text(json.dumps(lineage, indent=2) + '\n')
    shutil.copy2(REPO / 'LICENCE', root / 'LICENCE')
    if args.ros == 'ros1':
        guides = root / 'share/docs'
        guides.mkdir()
        for name in ['08_RK3588_WORKFLOW.md','09_DEPENDENCIES.md','11_RK3588_USER_GUIDE.md','12_VINS_REMOTE.md','13_BOARD_CLI.md']:
            original = REPO / 'docs' / name
            text = original.read_text()
            def source_link(match):
                label, target = match.group(1), match.group(2)
                path = (original.parent / target).resolve()
                kind = 'tree' if path.is_dir() else 'blob'
                return '[' + label + '](https://github.com/GoodLuck-123/VINS-Fusion/' + kind + '/' + metadata['packaging_commit'] + '/' + str(path.relative_to(REPO)) + ')'
            # Maintenance evidence/locks stay in Git, not in a runtime package.
            text = re.sub(r'\[([^\]]+)\]\((\.\./[^)]+)\)', source_link, text)
            (guides / name).write_text(text)
        (root / 'README.md').write_text(
            '# RK3588 ROS 1 ' + args.version + '\n\n## Quick Start\n\n'
            '在板端 bash 中执行：\n\n```bash\nsource /实际安装目录/env.sh\n'
            'check --arc --lib --sha --dir\n'
            'check --config --bag /数据路径/input.bag --output /项目路径/runs/demo01\n'
            'run --bag /数据路径/input.bag --name demo01\n```\n\n' +
            ('独立 CLI，无需安装 ROS 或编译工具。线程停止已修复并验证\n\n' if args.ros1_build_validation else
             '独立 CLI，无需安装 ROS 或编译工具。原节点停止 −6 缺陷保留，run 会报告失败，不能称正常退出\n\n') +
            '[板端 CLI 详情](share/docs/13_BOARD_CLI.md) · [用户指南](share/docs/11_RK3588_USER_GUIDE.md)\n')
    else:
        shutil.copy2(REPO / 'docs/11_RK3588_USER_GUIDE.md', root / 'README.md')
    files = [p for p in sorted(root.rglob('*')) if p.is_file()]
    (root / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(root)}\n' for p in files))
    archive = output / f'install-{args.ros}-{args.version}-linux-aarch64.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(root, arcname='install')
    (output / (archive.name + '.sha256')).write_text(f'{sha(archive)}  {archive.name}\n')
    host = output / 'host'
    host.mkdir()
    subprocess.run([str(REPO.parent / '.infra/bin/vins-remote'), '--print-config'],
                   check=True, stdout=subprocess.DEVNULL)
    shutil.copy2(REPO.parent / '.infra/bin/vins-remote', host / 'vins-remote')
    for name in ['deploy.py', 'run.py', 'remote_settings.py']:
        shutil.copy2(HERE / name, host / name)
    config = REPO.parent / '.infra/bin/vins-remote.conf'
    if config.exists():
        shutil.copy2(config, host / config.name)
    shutil.copy2(REPO / 'docs/12_VINS_REMOTE.md', host / 'README.md')
    (output / 'README.md').write_text(
        f'# {args.ros} {args.version}\n\n板端完整运行包：{archive.name}，解压顶层为 install/\n\n'
        '普通用户说明见 install/README.md；host/ 仅在 Ubuntu x86_64 主机运行\n'
        '无需上传本地 .infra/ 或在板端安装 ROS、OpenCV、Ceres\n')
    print(json.dumps(dict(directory=str(output), archive=str(archive), archive_sha256=sha(archive),
                          archive_bytes=archive.stat().st_size, verified_original_files=sum('base_sha256' not in item for item in lineage)), indent=2))


if __name__ == '__main__':
    main()
