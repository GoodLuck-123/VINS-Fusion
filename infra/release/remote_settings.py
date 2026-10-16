"""Shared host defaults resolved by the C++ tool, without an SSH connection."""
import json
from pathlib import Path
import shlex
import subprocess


def add_options(parser):
    parser.add_argument('--tool', type=Path)
    parser.add_argument('--config', type=Path, help='Shared vins-remote key=value defaults')
    parser.add_argument('--root', help='Override the board workspace for this invocation')


def load(args):
    here = Path(__file__).resolve().parent
    tool = args.tool or (here / 'vins-remote' if (here / 'vins-remote').exists()
                         else here.parents[2] / '.infra/bin/vins-remote')
    options = []
    if args.config:
        options += ['--config', str(args.config.resolve())]
    if args.root:
        options += ['--root', args.root]
    settings = json.loads(subprocess.check_output([str(tool), *options, '--print-config'], text=True))
    return tool, options, settings


def remote_path(value):
    if value.startswith('/'):
        return shlex.quote(value)
    if value == '~':
        return '"$HOME"'
    if value.startswith('~/'):
        value = value[2:]
    return '"$HOME"/' + shlex.quote(value)


EVENT_SHELL = '''event() {
  if declare -F vins_event >/dev/null; then vins_event "$@";
  else printf '[%s] %s\\n' "$1" "${2:-}"; fi
}
'''
