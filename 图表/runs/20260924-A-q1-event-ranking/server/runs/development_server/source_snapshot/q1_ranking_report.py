"""Validate proposal accounting and summarize independent ranking ablations."""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from q1_io import write_json
from q1_ablation_report import collect, compare


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    summary = collect(args.runs)
    searches, counts = {}, Counter()
    for row in summary['runs']:
        key = row['case'], row['cores'], row['seed'], row['config']
        run = args.runs/f'{key[0]}_{key[1]}cores_seed{key[2]}_{key[3]}'
        s = json.loads((run/'search.json').read_text(encoding='utf-8'))
        searches[key] = s
        evidence = {r['evaluation_id']:r for r in s['proposal_ledger'] if r['status']=='evaluated'}
        assert len(evidence) == len(s['evaluations']) == summary['evaluation_budget']
        for r in s['proposal_ledger']:
            if r['status']=='duplicate':
                assert r['plan_sha256']==evidence[r['evaluation_id']]['plan_sha256']
        assert len(s['protected_grain_ledger'])==4
        for r in s['protected_grain_ledger']:
            assert r['status'] in {'evaluated','duplicate','infeasible'}
            counts[r['status']] += 1
        for b in s['boundary_stats']:
            if b.get('kind') == 'local_exact':
                assert b['probes'] <= 24 and len(b['walk_scores']) <= 6
                assert all(len(r)<=12 for r in b['regions'])
                assert b['preparation']['global_evaluations']==0
        row['solver_seconds'] = s['elapsed_seconds']
        row['local_prepare_seconds'] = sum(b.get('preparation',{}).get('seconds',0) for b in s['boundary_stats'])
        result = json.loads(gzip.decompress((run/'evaluation.json.gz').read_bytes()))
        row['added_copy_bytes'] = result['data_movement_bytes']['added_copy_bytes']
    comparisons = []
    for before, after in [('shared_region','shared_exact'),
                          ('shared_exact','shared_exact_wide'),
                          ('shared_exact','shared_exact_uphill')]:
        comp = compare(summary['runs'],before,after)
        for field in ['makespan','added_copy_bytes','solver_seconds','local_prepare_seconds']:
            comp[field] = {c:sum(r[field] for r in summary['runs'] if r['config']==c)
                           for c in [before,after]}
        comparisons.append(comp)
    prefix_checked = 0
    for key,s in searches.items():
        if key[-1]=='shared_region':
            continue
        base = searches[key[:3]+('shared_region',)]
        n = next((i for i,e in enumerate(s['evaluations']) if e['candidate'].startswith('region_')),None)
        if n is not None:
            fields = lambda h: [(x['candidate'],x['makespan'],x['added_copy_bytes']) for x in h]
            assert fields(s['evaluations'][:n]) == fields(base['evaluations'][:n])
            prefix_checked += 1
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'comparison.json', {'completed':True,'comparisons':comparisons,
               'grain_status_counts':dict(counts),'prefix_checked':prefix_checked,
               'global_calls':sum(r['official_calls'] for r in summary['runs']),
               'note':'Same global evaluation budget, not same wall-clock budget; development cases.'})


if __name__=='__main__':
    main()
