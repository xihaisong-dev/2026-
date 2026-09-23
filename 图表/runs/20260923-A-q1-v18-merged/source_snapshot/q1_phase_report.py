"""Verify parallel runs, budget ledgers and per-core paired phase-ranking results."""
import argparse
import gzip
import json
from pathlib import Path
from collections import Counter
from q1_io import write_json
from q1_ablation_report import collect,compare


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs',type=Path,required=True)
    ap.add_argument('--previous',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    summary=collect(args.runs)
    rows=summary['runs']; searches={};grain=Counter()
    for r in rows:
        key=(r['case'],r['cores'],r['seed'],r['config'])
        folder=args.runs/f'{key[0]}_{key[1]}cores_seed{key[2]}_{key[3]}'
        s=json.loads((folder/'search.json').read_text(encoding='utf-8'))
        searches[key]=s
        evidence={x['evaluation_id']:x for x in s['proposal_ledger'] if x['status']=='evaluated'}
        assert len(evidence)==summary['evaluation_budget']
        for x in s['proposal_ledger']:
            if x['status']=='duplicate':
                assert x['plan_sha256']==evidence[x['evaluation_id']]['plan_sha256']
        assert len(s['protected_grain_ledger'])==4
        grain.update(x['status'] for x in s['protected_grain_ledger'])
        result=json.loads(gzip.decompress((folder/'evaluation.json.gz').read_bytes()))
        r['added_copy_bytes']=result['data_movement_bytes']['added_copy_bytes']
        r['prepare_seconds']=sum(b.get('preparation',{}).get('seconds',0) for b in s['boundary_stats'])
        r['phase_seconds']=sum(b.get('preparation',{}).get('phase_seconds',0) for b in s['boundary_stats'])
    configs=sorted({r['config'] for r in rows})
    totals={c:{f:sum(r[f] for r in rows if r['config']==c)
               for f in ['makespan','added_copy_bytes','seconds','prepare_seconds','phase_seconds']}
            for c in configs}
    comparisons=[compare(rows,a,b) for a,b in [('shared_region','shared_exact'),
                 ('shared_region','shared_phase'),('shared_exact','shared_phase')]]
    per_core=[]
    for core in sorted({r['cores'] for r in rows}):
        group=[r for r in rows if r['cores']==core]
        per_core.append({'cores':core,'totals':{c:sum(r['makespan'] for r in group if r['config']==c) for c in configs},
                         'comparison':compare(group,'shared_region','shared_phase')})
    checked=0
    for key,s in searches.items():
        if key[-1]=='shared_region':continue
        n=next((i for i,r in enumerate(s['evaluations']) if r['candidate'].startswith('region_')),None)
        if n is not None:
            fields=lambda h:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in h]
            assert fields(s['evaluations'][:n])==fields(searches[key[:3]+('shared_region',)]['evaluations'][:n])
            checked+=1
    previous=collect(args.previous); old_checked=0
    now={(r['case'],r['cores'],r['seed'],r['config']):r for r in rows}
    for r in previous['runs']:
        key=(r['case'],r['cores'],r['seed'],r['config'])
        if key in now:
            assert r['makespan']==now[key]['makespan']
            old_checked+=1
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'comparison.json',{'completed':True,'totals':totals,
        'comparisons':comparisons,'per_core':per_core,'grain_ledger_counts':dict(grain),
        'prefix_checked':checked,'previous_serial_results_checked':old_checked,
        'global_calls':sum(r['official_calls'] for r in rows),'workers':summary['workers'],
        'wall_seconds':summary['wall_seconds'],'same_wall_budget':False})


if __name__=='__main__':main()
