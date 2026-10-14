"""Verify frozen board evidence and unchanged ROS 1/ROS 2 core source trees."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[3]


def verify(repo, reference, ros2=False):
    manifests = []
    originals = 0
    directory = repo / 'infra/rk3588/reference'
    for manifest in sorted(directory.rglob('SHA256SUMS')):
        entries = manifest.read_text().splitlines()
        for line in entries:
            sha, name = line.split('  ', 1)
            path = manifest.parent / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise RuntimeError(f'Archive hash changed: {path}')
        manifests.append(dict(path=str(manifest.relative_to(repo)), files=len(entries)))
    for summary in sorted(directory.rglob('summary.json')):
        data = json.loads(summary.read_text())
        for name, sha in data.get('original_file_sha256', {}).items():
            path = summary.parent / name
            payload = path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes())
            if hashlib.sha256(payload).hexdigest() != sha:
                raise RuntimeError(f'Original/decompressed hash changed: {path}')
            originals += 1
    core = ['camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion', 'config']
    if ros2:
        core.append('ros2')
    if subprocess.check_output(['git', '-C', str(repo), 'diff', reference, '--', *core]):
        raise RuntimeError(f'Core/config changed from {reference}: {repo}')
    return dict(repo=str(repo), reference=reference, manifests=manifests,
                manifest_entries=sum(item['files'] for item in manifests),
                original_decompressed_files=originals, core_config_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ros1-repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(status='pass', ros2=verify(REPO, '7d42fac', ros2=True),
                  ros1=verify(args.ros1_repo.resolve(), '8c7c8d2'))
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    for name in ['ros2', 'ros1']:
        item = result[name]
        print(f'{name}: {len(item["manifests"])} archives / {item["manifest_entries"]} entries, '
              f'{item["original_decompressed_files"]} original hashes, core/config unchanged')


if __name__ == '__main__':
    main()
