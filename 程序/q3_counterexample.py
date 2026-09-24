"""Explain the largest observed L2 regression through fixed-run critical paths."""
import argparse,json,gzip
from pathlib import Path
from collections import defaultdict
from q1_io import PROCESSED,ROOT,write_json
from q3_solver import load
from q2_bottleneck_j import analyze


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();settings,delay,_,_=load()
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    case,n=67,2
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'))
    plan=json.loads((ROOT/f'图表/runs/20260924-A-q2-delivery-r07/solutions/{n}cores/case_{case:03}_multicore_res.json').read_text(encoding='utf-8'))
    tasks,links,_,_,_=_build_scene_b_tasks(raw,plan,settings['bandwidth'],settings['capacity'])
    rows={}
    for mode in ['no_l2','fixed_l2']:
        with gzip.open(a.run/f'case_{case:03}/{n}/{mode}.json.gz','rt',encoding='utf-8') as f:r=json.load(f)
        d=analyze(tasks,links,r,delay,settings['bandwidth']);totals=defaultdict(int)
        entries={(c['core_id'],o['op_id']):o for c in r['per_core_timeline'] for o in c['ops']}
        for x in d['critical_chain']:
            op=entries[x['core'],x['op']];kind=op.get('memory_path',op['pipe'])
            totals[kind]+=x['end']-x['start'];totals['synchronization_lag']+=x['incoming_lag']
        assert sum(totals.values())==r['makespan']
        rows[mode]=dict(makespan=r['makespan'],critical_path_cycles=dict(totals),start_reconstruction_error=d['start_reconstruction_max_error'],
                       cache_stats=r.get('cache_stats'),critical_chain=d['critical_chain'])
    write_json(a.output,dict(case=case,cores=n,selection='largest fixed-plan L2 regression among 500 configurations; post-hoc diagnostic',
                            caveat='Observed durations and critical chains explain these runs, not isolated causal or additive counterfactual savings.',runs=rows))
    print({k:{x:v[x] for x in ['makespan','critical_path_cycles']} for k,v in rows.items()})


if __name__=='__main__':main()
