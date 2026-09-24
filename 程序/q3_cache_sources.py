"""Post-hoc mechanistic diagnostics: distinguish reload and cross-core cache reads."""
import argparse,json
from collections import defaultdict
from pathlib import Path
from q1_io import PROCESSED,write_json
from q3_solver import load,evaluate,audit
from q3_run import SEEDS,dump_gz


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);s,d,c,_=load()
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    allrows=[]
    for case,n in [(44,1),(46,1),(5,5)]:
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text())
        plan=json.loads((SEEDS/f'{n}cores/case_{case:03}_multicore_res.json').read_text())
        tasks,links,_,_,_=_build_scene_b_tasks(raw,plan,s['bandwidth'],s['capacity'])
        cross={(x['target_core'],x['target_copy_in_id']) for x in links}
        r=evaluate(raw,plan,s,d,c);audit(raw,plan,r,s,d);counts=defaultdict(lambda:defaultdict(int))
        for e in r['cache_events']:
            if e['event'] not in ('hit','miss'):continue
            task=tasks[e['core_id']];o=e['op_id']
            ts=[task['tensor_by_id'][tid] for tid in task['out_tids'][o] if task['tensor_by_id'][tid]['pos']!='DDR']
            reload=any(t.get('logical_tid',t['id'])!=t['id'] for t in ts)
            kind='spill_reload' if reload else 'cross_core_input' if (e['core_id'],o) in cross else 'original_input'
            counts[kind][e['event']+'_bytes']+=e['size_bytes'];counts[kind][e['event']+'_count']+=1
        assert sum(x.get('hit_bytes',0) for x in counts.values())==r['cache_stats']['hit_bytes']
        dump_gz(a.output/f'case_{case:03}_{n}.json.gz',r)
        allrows.append(dict(case=case,cores=n,makespan=r['makespan'],cache_stats=r['cache_stats'],sources=dict(counts)))
    write_json(a.output/'sources.json',dict(selection='case044 and case046 selected after observing single-core high hit rates; case005 predeclared development case',rows=allrows))
    raw=json.loads((PROCESSED/'data/case_044.json').read_text());plan=json.loads((SEEDS/'1cores/case_044_multicore_res.json').read_text())
    sweep=[]
    for cap in [0,65536,131072,262144,524288,1048576,2097152]:
        r=evaluate(raw,plan,s,d,dict(c,cache_capacity_bytes=cap));audit(raw,plan,r,s,d)
        sweep.append(dict(capacity=cap,makespan=r['makespan'],hit_rate=r['cache_stats']['hit_rate']))
    write_json(a.output/'singlecore_capacity.json',sweep)
    print(json.dumps(allrows))


if __name__=='__main__':main()
