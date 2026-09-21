"""Lightweight collaboration scaffold check, not competition acceptance."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'README.md', 'CONTRIBUTING.md', '00_admin/TEAM.md',
    '00_admin/handoffs/TEMPLATE.md', '00_admin/workflow.json',
    '01_problem/original', '02_retrieval', '03_model', '04_code',
    '05_results/runs', '06_paper/sections', '07_review',
)


def main():
    errors = [f'Missing: {p}' for p in REQUIRED if not (ROOT / p).exists()]
    count = 0
    for dirname in ('00_admin', '01_problem', '02_retrieval', '03_model',
                    '04_code', '05_results', '06_paper', '07_review'):
        for path in sorted((ROOT / dirname).rglob('*.json')):
            if any(part in {'.venv', 'venv', 'node_modules', '__pycache__'}
                   for part in path.relative_to(ROOT).parts):
                continue
            count += 1
            try:
                json.loads(path.read_text(encoding='utf-8-sig'))
            except (ValueError, OSError) as exc:
                errors.append(f'{path.relative_to(ROOT)}: {exc}')
    for error in errors:
        print(error)
    print(f'Checked required paths and {count} JSON files; errors={len(errors)}.')
    print('This check does not certify competition gates, results, or handoff acceptance.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
