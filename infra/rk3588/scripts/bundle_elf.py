"""Bundle one ARM ELF and its shared-library closure; retain the board's glibc."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

# These are one ABI unit with the board's dynamic loader; never ship a partial glibc.
SYSTEM_LIBS = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2',
               'librt.so.1', 'libresolv.so.2', 'libutil.so.1', 'ld-linux-aarch64.so.1'}


def needed(path):
    with path.open('rb') as stream:
        header = stream.read(20)
    if header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', header, 18)[0] != 183:
        raise RuntimeError(f'Expected little-endian ELF64 AArch64: {path}')
    dynamic = subprocess.check_output(['/usr/bin/readelf', '--dynamic', str(path)], text=True)
    return re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--sysroot', type=Path, required=True)
    parser.add_argument('--library-dir', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'lib').mkdir()
    directories = [*args.library_dir, args.sysroot / 'usr/lib/aarch64-linux-gnu',
                   args.sysroot / 'lib/aarch64-linux-gnu', args.sysroot / 'usr/lib']
    binary = output / args.executable.name
    shutil.copy2(args.executable, binary)
    pending = needed(binary)
    copied = set()
    while pending:
        soname = pending.pop()
        if soname in SYSTEM_LIBS or soname in copied:
            continue
        if Path(soname).name != soname:
            raise RuntimeError(f'Unexpected DT_NEEDED path: {soname}')
        source = next((d / soname for d in directories if (d / soname).is_file()), None)
        if source is None:
            raise RuntimeError(f'Target shared library missing: {soname}')
        pending.extend(needed(source))
        shutil.copy2(source, output / 'lib' / soname)
        copied.add(soname)
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{binary.name}: {len(copied)} ARM runtime libraries; system glibc retained')


if __name__ == '__main__':
    main()
