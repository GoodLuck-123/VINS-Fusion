"""Verify both historical manifest conventions and unchanged original Git snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from workspace_paths import DESKTOP_ROOT, REPO_ROOT


def verify(historical_ref):
    manifests = []
    for manifest in sorted(DESKTOP_ROOT.rglob('SHA256SUMS')):
        entries = manifest.read_text().splitlines()
        for line in entries:
            expected, name = line.split('  ', 1)
            # The first six WSL manifests use the desktop root; later ones use
            # their snapshot directory. Preserve the original files verbatim.
            root = (DESKTOP_ROOT if name.startswith(('baseline_reference/', 'ros2_reference/',
                                                     'comparison_reference/')) else manifest.parent)
            path = root / name
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError(f'SHA256 mismatch: {path}')
        manifests.append(dict(directory=str(manifest.parent.relative_to(REPO_ROOT)), files=len(entries)))
    records = subprocess.check_output(['git', 'ls-tree', '-rz', historical_ref,
                                      'infra/desktop/baseline_reference', 'infra/desktop/ros2_reference',
                                      'infra/desktop/comparison_reference'], cwd=REPO_ROOT).split(b'\0')
    originals = 0
    for record in records:
        if not record:
            continue
        meta, name = record.split(b'\t', 1)
        _, kind, expected = meta.split()
        if kind != b'blob':
            raise RuntimeError(f'Unexpected historical object: {name!r}')
        data = (REPO_ROOT / name.decode()).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest().encode()
        if actual != expected:
            raise RuntimeError(f'Historical snapshot changed: {name.decode()}')
        originals += 1
    if not originals:
        raise RuntimeError('Historical reference contains no snapshot files')
    return dict(historical_ref=historical_ref, manifests=manifests,
                total_manifest_entries=sum(row['files'] for row in manifests),
                original_snapshot_blobs_unchanged=originals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical-ref', default='b250dc0')
    parser.add_argument('--output', type=Path, help='Create a new JSON audit; refuse to overwrite an existing file')
    args = parser.parse_args()
    result = json.dumps(verify(args.historical_ref), indent=2) + '\n'
    if args.output:
        with args.output.open('x') as stream:
            stream.write(result)
    print(result, end='')


if __name__ == '__main__':
    main()
