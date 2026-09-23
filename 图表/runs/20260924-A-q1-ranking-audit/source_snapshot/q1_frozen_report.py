"""Verified fixed-state audit and matched-budget ablation summary."""
import argparse
import gzip
import json
from pathlib import Path
from q1_io import sha, write_json
from q1_ablation_report import collect, compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', nargs='+', type=Path, required=True)
    p.add_argument('--runs', nargs='+', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    base, new, files, inputs, ziphash = {}, [], {}, {}, set()
    def key(r): return r['case'],r['cores'],r['seed']
    for kind, folders in [('base',args.baseline),('new',args.runs)]:
        for folder in folders:
            summary = collect(folder)
            if summary['evaluation_budget'] != 12: raise ValueError('Budget mismatch')
            ziphash.add(summary['source_zip_sha256'])
            for name,h in summary['input_sha256'].items():
                if name in inputs and inputs[name] != h: raise ValueError('Input mismatch')
                inputs[name] = h
            for row in summary['runs']:
                if kind == 'base' and row['config'] != 'shared_region': continue
                r = dict(row)
                run = folder/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}"
                s = json.loads((run/'search.json').read_text(encoding='utf-8'))
                result = json.loads(gzip.decompress((run/'evaluation.json.gz').read_bytes()))
                r['added_copy_bytes'] = result['data_movement_bytes']['added_copy_bytes']
                files[(key(r),r['config'])] = s
                if kind == 'base':
                    if key(r) in base: raise ValueError('Duplicate baseline')
                    base[key(r)] = r
                else:
                    assert s['protected_grain_attempts'] == [.5,1.,2.,.25]
                    assert s['region_attempts'] <= 1
                    assert all(x['boundary_probes'] <= 12 and x['accepted_steps'] <= 3 for x in s['boundary_stats'])
                    new.append(r)
    if len(ziphash) != 1: raise ValueError('Source ZIP mismatch')
    configs = sorted({r['config'] for r in new})
    groups = {c: [r for r in new if r['config']==c] for c in configs}
    keys = {key(r) for r in groups[configs[0]]}
    if any({key(r) for r in rows} != keys or len(rows) != len(keys) for rows in groups.values()):
        raise ValueError('Unmatched configurations')
    comparisons = []; checked = 0
    for c, rows in groups.items():
        refs = [base[key(r)] for r in rows]
        x = compare(refs+rows, 'shared_region',c)
        a,b = sum(r['makespan'] for r in refs),sum(r['makespan'] for r in rows)
        x.update(before_total=a,after_total=b,reduction_percent=100*(1-b/a),
                 before_copy_bytes=sum(r['added_copy_bytes'] for r in refs),
                 after_copy_bytes=sum(r['added_copy_bytes'] for r in rows))
        comparisons.append(x)
        for r in rows:
            s,old = files[(key(r),c)],files[(key(r),'shared_region')]
            idx = next((i for i,e in enumerate(s['evaluations']) if e['candidate'].startswith('region_')),None)
            if idx is not None:
                fields = lambda es: [(e['candidate'],e['makespan']) for e in es]
                if fields(s['evaluations'][:idx]) != fields(old['evaluations'][:idx]):
                    raise ValueError('Changed pre-region history')
                checked += 1
    audit = json.loads((args.audit/'audit.json').read_text(encoding='utf-8'))
    assert audit['completed']
    for name,h in audit['code_sha256'].items():
        assert sha((args.audit/'source_snapshot'/name).read_bytes()) == h
    count = 0
    for i,item in enumerate(audit['runs']):
        folder, = args.audit.glob(f'{i:02d}_*')
        for row in item['rows']:
            for name,h in row['artifacts'].items(): assert sha((folder/name).read_bytes()) == h
            count += 1
    assert count == audit['official_calls']
    ranking = {f: {'discordant':sum(r['rankings'][f]['discordant'] for r in audit['runs']),
                   'comparable':sum(r['rankings'][f]['comparable'] for r in audit['runs']),
                   'top_regret_cycles_sum':sum(r['rankings'][f]['top_regret_cycles'] or 0 for r in audit['runs'])}
               for f in ['base','fluid','calibrated','oracle_local_replay']}
    report = {'new_solver_runs':len(new),'new_solver_official_calls':sum(r['official_calls'] for r in new),
              'separate_audit_official_calls':count,'prefix_pairs_checked':checked,
              'comparisons':comparisons,'audit_rankings':ranking,
              'solver_stats':[{'case':r['case'],'cores':r['cores'],'seed':r['seed'],'config':r['config'],
                              'boundary_stats':files[(key(r),r['config'])]['boundary_stats']} for r in new]}
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'comparison.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['solver_stats','comparisons']},indent=2))
    for c in comparisons: print(json.dumps({k:v for k,v in c.items() if k!='pairs'},indent=2))


if __name__ == '__main__': main()
