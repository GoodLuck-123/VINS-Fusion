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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ros', choices=['ros1', 'ros2'], required=True)
    parser.add_argument('--version', default='v0.1')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--addon', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New release directory, outside the Git checkout')
    args = parser.parse_args()
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
                    known_limitations=['ROS1 original sync-thread shutdown abort retained'] if args.ros == 'ros1' else [])
    (root / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (root / 'share/provenance/file_lineage.json').write_text(json.dumps(lineage, indent=2) + '\n')
    shutil.copy2(REPO / 'LICENCE', root / 'LICENCE')
    if args.ros == 'ros1':
        guides = root / 'share/docs'
        guides.mkdir()
        for name in ['08_RK3588_WORKFLOW.md','09_DEPENDENCIES.md','11_RK3588_USER_GUIDE.md','12_VINS_REMOTE.md','13_BOARD_CLI.md']:
            shutil.copy2(REPO / 'docs' / name, guides / name)
        (root / 'README.md').write_text(
            '# RK3588 ROS 1 ' + args.version + '\n\n## Quick Start\n\n'
            '在板端 bash 中执行：\n\n```bash\nsource /实际安装目录/env.sh\n'
            'check --arc --lib --sha --dir\n'
            'check --config --bag /数据路径/input.bag --output /项目路径/runs/demo01\n'
            'run --bag /数据路径/input.bag --name demo01\n```\n\n'
            '独立 CLI，无需安装 ROS 或编译工具。原节点停止 −6 缺陷保留，run 会报告失败，不能称正常退出\n\n'
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
                          archive_bytes=archive.stat().st_size, verified_original_files=len(lineage)), indent=2))


if __name__ == '__main__':
    main()
