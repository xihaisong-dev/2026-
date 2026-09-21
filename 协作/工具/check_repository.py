"""Check the single workflow, source snapshot and JSON; not contest acceptance."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/meta-model-agent'
LEGACY = ('00_admin', '01_problem', '02_retrieval', '03_model',
          '04_code', '05_results', '06_paper', '07_review', 'tools')


def main():
    errors = []
    required = ('mm.py', '协作/分工.md', '协作/交接/TEMPLATE.md',
                '状态/工作流状态.json', '状态/工作流清单快照.json',
                '题目/赛题原件', '题目/官方论文模板', '数据/processed')
    for path in required:
        if not (ROOT / path).exists():
            errors.append(f'Missing: {path}')
    for path in LEGACY:
        if (ROOT / path).exists():
            errors.append(f'Legacy workflow still present: {path}')
    for path in ROOT.rglob('*.json'):
        if any(p in {'.git', '.venv', 'venv', '__pycache__'}
               for p in path.relative_to(ROOT).parts):
            continue
        try:
            json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    try:
        lock = json.loads((ROOT / '协作/技能版本锁.json').read_text(encoding='utf-8'))
        expected_files = lock['files_sha256']
        actual_files = {p.relative_to(SKILL).as_posix() for p in SKILL.rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts
                        and p.suffix not in {'.pyc', '.pyo'}}
        if actual_files != set(expected_files):
            errors.append('Skill snapshot file list differs from version lock')
        for relative, expected in expected_files.items():
            path = SKILL / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append(f'Skill snapshot changed: {relative}')
        manifest = json.loads((SKILL / 'assets/workflow_manifest.json').read_text(encoding='utf-8'))
        state = json.loads((ROOT / '状态/工作流状态.json').read_text(encoding='utf-8'))
        if state['competition'] != 'gmcm':
            errors.append('Competition must be gmcm')
        if [s['stage_id'] for s in state['steps']] != [s['stage_id'] for s in manifest['steps']]:
            errors.append('Workflow stages differ from pinned manifest')
    except (OSError, ValueError, KeyError) as exc:
        errors.append(f'Workflow configuration: {exc}')
    for error in errors:
        print(error)
    print(f'Repository checks: {len(errors)} errors; this is not contest acceptance.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
