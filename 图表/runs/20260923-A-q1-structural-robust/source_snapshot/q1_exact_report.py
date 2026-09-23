"""Integrity checks and candidate-budget-matched exact-placement comparisons."""
import argparse
import gzip
import json
from pathlib import Path
from q1_ablation_report import collect
from q1_io import sha, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--polish', type=Path, required=True)
    p.add_argument('--control', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    polish = json.loads((args.polish/'summary.json').read_text(encoding='utf-8'))
    if not polish['completed']:
        raise ValueError('Incomplete polishing batch')
    for name, expected in polish['source_code_sha256'].items():
        if sha((args.polish/'source_snapshot'/name).read_bytes()) != expected:
            raise ValueError('Source snapshot mismatch')
    control = collect(args.control)
    reference = {(r['case'], r['cores'], r['seed']): r for r in control['runs']}
    rows, excluded = [], []
    for r in polish['runs']:
        folder = args.polish/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_beam"
        for name, expected in r['artifacts'].items():
            if sha((folder/name).read_bytes()) != expected:
                raise ValueError('Polish artifact mismatch')
        result = json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))
        if (result['makespan'], result['data_movement_bytes']['added_copy_bytes']) != (r['after'], r['after_added']):
            raise ValueError('Metric mismatch')
        key = (r['case'], r['cores'], r['seed'])
        if key not in reference:
            raise ValueError('Missing control')
        budget = polish['baseline_evaluations_per_run'] + r['extra_global_evaluations']
        if budget != control['evaluation_budget']:
            excluded.append({'key': key, 'polish_candidates': budget,
                             'control_candidates': control['evaluation_budget']})
            continue
        rows.append({'case': r['case'], 'cores': r['cores'], 'seed': r['seed'],
                     'control': reference[key]['makespan'], 'polish': r['after']})
    before = sum(r['control'] for r in rows)
    after = sum(r['polish'] for r in rows)
    report = {'scope': 'Equal candidate count; polish final verification is extra overhead',
              'rows': rows, 'excluded': excluded, 'control_sum': before, 'polish_sum': after,
              'reduction_percent': 100*(1-after/before),
              'wins': sum(r['polish'] < r['control'] for r in rows),
              'ties': sum(r['polish'] == r['control'] for r in rows),
              'losses': sum(r['polish'] > r['control'] for r in rows),
              'input_hashes': {str(f): sha(f.read_bytes()) for f in
                              [args.polish/'summary.json', args.control/'summary.json']}}
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'comparison.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'rows', 'input_hashes'}}, ensure_ascii=True))


if __name__ == '__main__':
    main()
