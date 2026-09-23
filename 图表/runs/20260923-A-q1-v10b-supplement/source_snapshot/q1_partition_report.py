"""Verify protected opportunities and report independent partition ablations."""
import argparse
import gzip
import json
from pathlib import Path
from q1_ablation_report import collect
from q1_io import write_json, sha


def summarize(rows, before, after):
    by = lambda config: {(r['case'], r['cores'], r['seed']): r for r in rows if r['config'] == config}
    a, b = by(before), by(after)
    if a.keys() != b.keys() or not a:
        raise ValueError('Unmatched pairs')
    pairs = [{'case': k[0], 'cores': k[1], 'seed': k[2], 'before': a[k]['makespan'],
              'after': b[k]['makespan'], 'before_added': a[k]['added'], 'after_added': b[k]['added']}
             for k in sorted(a)]
    bt, at = sum(r['before'] for r in pairs), sum(r['after'] for r in pairs)
    bb, ab = sum(r['before_added'] for r in pairs), sum(r['after_added'] for r in pairs)
    return {'before_config': before, 'after_config': after, 'pairs': pairs,
            'wins': sum(r['after'] < r['before'] for r in pairs),
            'ties': sum(r['after'] == r['before'] for r in pairs),
            'losses': sum(r['after'] > r['before'] for r in pairs),
            'before_time': bt, 'after_time': at, 'time_reduction_percent': 100*(1-at/bt),
            'before_added': bb, 'after_added': ab,
            'added_reduction_percent': 100*(1-ab/bb) if bb else None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, nargs='+', required=True)
    p.add_argument('--baseline-runs', type=Path, nargs='*', default=[])
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    rows, histories, sources = [], {}, {}
    prefix_labels = {'single_task', 'greedy', 'multilevel', 'grain_0.5', 'grain_1.0', 'grain_2.0', 'grain_0.25'}
    def prefix(history):
        result = []
        for row in history:
            if row['candidate'] not in prefix_labels:
                break
            result.append((row['candidate'], row['makespan'], row['added_copy_bytes']))
        return result
    stats = []
    for folder in args.runs + args.baseline_runs:
        summary = collect(folder)
        sources[str(folder)] = sha((folder/'summary.json').read_bytes())
        for row in summary['runs']:
            if folder in args.baseline_runs and row['config'] != 'insertion_rank':
                continue
            key = (row['case'], row['cores'], row['seed'], row['config'])
            if key in histories:
                raise ValueError('Duplicate experiment key')
            run = folder/f"{row['case']}_{row['cores']}cores_seed{row['seed']}_{row['config']}"
            history = json.loads((run/'search.json').read_text(encoding='utf-8'))
            histories[key] = history['evaluations']
            if row['config'] != 'insertion_rank' and history['protected_grain_attempts'] != [.5, 1., 2., .25]:
                raise ValueError('Protected grain attempts missing')
            result = json.loads(gzip.decompress((run/'evaluation.json.gz').read_bytes()))
            row['added'] = result['data_movement_bytes']['added_copy_bytes']
            if history.get('shared_input_stats'):
                stats.append({'case': row['case'], 'cores': row['cores'], 'seed': row['seed'],
                              **history['shared_input_stats']})
            rows.append(row)
    checked = 0
    for key in histories:
        if key[-1] == 'local_repair':
            if prefix(histories[key]) != prefix(histories[(*key[:3], 'partition_guard')]):
                raise ValueError('Repair changed protected partition prefix')
            checked += 1
    comparisons = [('insertion_rank', 'partition_guard'), ('partition_guard', 'shared_input'),
                   ('partition_guard', 'local_repair'), ('insertion_rank', 'shared_input')]
    report = {'source_summaries': sources, 'complete_runs': len(rows),
              'actual_official_calls': sum(r['official_calls'] for r in rows),
              'repair_prefix_pairs_checked': checked, 'shared_input_stats': stats,
              'comparisons': [summarize(rows, a, b) for a, b in comparisons],
              'by_core': {str(c): [summarize([r for r in rows if r['cores'] == c], a, b)
                                    for a, b in comparisons] for c in sorted({r['cores'] for r in rows})}}
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'comparison.json', report)
    print(json.dumps([{k: v for k, v in r.items() if k != 'pairs'} for r in report['comparisons']], ensure_ascii=True))


if __name__ == '__main__':
    main()
