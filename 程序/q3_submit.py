"""Graph-to-plan Q3 entry. Optional Q2 seed; cold mode computes adopted Q2 first."""
import argparse,json,time
from pathlib import Path
from q1_io import PROCESSED,official,sha,write_json
from q3_solver import load,solve
from q3_run import dump_gz


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path);p.add_argument('-n','--cores',type=int,required=True,choices=range(1,6))
    p.add_argument('--seed',type=Path);p.add_argument('--budget',type=int,default=4)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv);assert a.budget>=0 and not a.output.exists()
    settings,delay,cache,provenance=load();raw=json.loads(a.graph.read_text(encoding='utf-8-sig'))
    t=time.perf_counter()
    if a.seed:seed=json.loads(a.seed.read_text(encoding='utf-8-sig'))
    elif a.cores==1:
        from singlecore_evaluate import build_singlecore_plan
        seed=build_singlecore_plan(raw)
    else:
        from q1_experimental import solve_experimental
        from q1_submit import BASELINE_FEATURES
        from q2_reserve_fast import solve as solve_b
        waits=official().read_scene_a_config(str(PROCESSED/'data/config.txt'))
        migration,_,_=solve_experimental(raw,settings,waits,a.cores,12,0,BASELINE_FEATURES,evaluator_backend='counter')
        seed,_,_=solve_b(raw,settings,delay,provenance,a.cores,migration)
    if len(seed['core_schedules'])!=a.cores:raise ValueError('Seed core count mismatch')
    seed_seconds=time.perf_counter()-t
    plan,r,anchor,stats=solve(raw,seed,settings,delay,cache,a.budget)
    a.output.mkdir(parents=True)
    write_json(a.output/f'{a.graph.stem}_multicore_res.json',plan)
    write_json(a.output/'seed.json',seed);write_json(a.output/'search.json',stats)
    dump_gz(a.output/'evaluation.json.gz',r)
    write_json(a.output/'run.json',dict(input_sha256=sha(a.graph.read_bytes()),provenance=provenance,
             seed_seconds=seed_seconds,seed_source='imported' if a.seed else 'cold_Q2_r07',
             makespan=r['makespan'],seed_l2_makespan=anchor['makespan'],cache=cache))
    print(r['makespan'])


if __name__=='__main__':main()
