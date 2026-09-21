"""Portable command forwarding to the repository's pinned Meta-model-agent."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / '.agents' / 'skills' / 'meta-model-agent' / 'scripts'
COMMANDS = {
    'stage': 'stage_executor.py',
    'pipeline': 'pipeline_manager.py',
    'init': 'workspace_init.py',
    'intake': 'problem_intake.py',
    'ai': 'ai_disclosure.py',
    'review': 'championship_review.py',
}


def main():
    args = sys.argv[1:]
    if not args or args[0] in {'-h', '--help'}:
        print('Usage: python mm.py <stage|pipeline|init|intake|ai|review> [arguments]')
        print('Example: python mm.py stage current')
        print('Defaults: repository workspace; init uses gmcm and PDF.')
        return 0
    command = args.pop(0)
    if command not in COMMANDS:
        print(f'Unknown command: {command}', file=sys.stderr)
        return 2
    if not any(a == '--workspace' or a.startswith('--workspace=') for a in args):
        args.extend(['--workspace', str(ROOT)])
    if command == 'init':
        for option, value in (('--competition', 'gmcm'), ('--output-format', 'pdf')):
            if not any(a == option or a.startswith(option + '=') for a in args):
                args.extend([option, value])
    return subprocess.run(
        [sys.executable, '-X', 'utf8', str(SCRIPTS / COMMANDS[command]), *args],
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == '__main__':
    raise SystemExit(main())
