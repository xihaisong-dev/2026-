"""Exercise pinned GMCM initialization and prerequisite blocking in isolation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def call(*args):
    return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'mm.py'), *args],
                          cwd=ROOT, capture_output=True, text=True, encoding='utf-8')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    with tempfile.TemporaryDirectory(prefix='mathmodel-migration-') as temporary:
        workspace = Path(temporary)
        init = call('init', '--workspace', temporary)
        require(init.returncode == 0, init.stdout + init.stderr)
        state_file = workspace / '状态/工作流状态.json'
        state = json.loads(state_file.read_text(encoding='utf-8'))
        require(state['competition'] == 'gmcm', 'Incorrect competition default')
        require(state['current_stage_id'] == 'DISCOVERY', 'Incorrect starting stage')
        require(state['ai_disclosure']['status'] == 'pending', 'AI choice was preselected')
        original = state_file.read_bytes()
        current = call('stage', 'current', '--workspace', temporary)
        require(current.returncode == 0, current.stdout + current.stderr)
        require(json.loads(current.stdout)['status'] == 'ready', 'Unexpected stage status')
        blocked = call('stage', 'begin', 'DISCOVERY', '--workspace', temporary)
        require(blocked.returncode != 0, 'Missing GMCM inputs were not blocked')
        require('赛题' in blocked.stderr and '模板' in blocked.stderr,
                'Failure was not the expected input prerequisite gate: ' + blocked.stderr)
        require(state_file.read_bytes() == original, 'Blocked begin changed workflow state')
        again = call('init', '--workspace', temporary)
        require(again.returncode == 0, again.stdout + again.stderr)
        require(state_file.read_bytes() == original, 'Repeated init replaced existing state')
    require(call('unknown-command').returncode != 0, 'Invalid wrapper command accepted')
    print('PASS: GMCM defaults, portable current, missing-input block, state preservation, repeat init.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
