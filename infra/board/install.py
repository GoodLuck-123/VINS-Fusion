"""Internal packaging helper: add standalone Python check/run entry points."""
import os
from pathlib import Path
import shutil
import sys


def install(root):
    root = Path(root)
    destination = root/'scripts/cli'
    destination.mkdir(parents=True,exist_ok=True)
    for name in ['common.py','bag_info.py','check.py','run.py']:
        shutil.copy2(Path(__file__).with_name(name),destination/name)
    for command in ['check','run']:
        entry = root/'bin'/command
        entry.parent.mkdir(parents=True,exist_ok=True)
        entry.write_text('''#!/usr/bin/python3 -I
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
os.environ['VINS_INSTALL_ROOT'] = str(root)
sys.path.insert(0, str(root/'scripts/cli'))
from COMMAND import main
try:
    sys.exit(main())
except KeyboardInterrupt:
    print('Check cancelled', file=sys.stderr)
    sys.exit(130)
'''.replace('COMMAND',command))
        entry.chmod(0o755)


if __name__=='__main__':install(sys.argv[1])
