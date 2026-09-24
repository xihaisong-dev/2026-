"""Current Q2 r07 submission: raw graph to standard solution, with optional seed."""
import argparse, gzip, json, time
from pathlib import Path
from q1_io import ROOT, PROCESSED, sha, write_json
from q2_evaluator import load
from q2_reserve_fast import solve
from q2_single_reference import fixed_reference_fast


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',required=True,type=int,choices=range(1,6))
    ap.add_argument('--migration',type=Path)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()
    assert not a.output.exists()
    start=time.perf_counter();settings,delay,provenance=load()
    raw=json.loads(a.graph.read_text(encoding='utf-8-sig'))
    arm='r07_reserve_fast'
    reference=fixed_reference_fast(raw,settings);migration_seconds=0.;migration_stats=None;migration=None
    if a.cores==1:
        from singlecore_evaluate import build_singlecore_plan
        plan=build_singlecore_plan(raw);result=reference;stats={'role':'prescribed_single_reference','slots':0}
    else:
        if a.migration:
            migration=json.loads(a.migration.read_text(encoding='utf-8-sig'))
        else:
            from q1_io import official
            from q1_experimental import solve_experimental
            from q1_submit import BASELINE_FEATURES
            waits=official().read_scene_a_config(str(PROCESSED/'data/config.txt'))
            t=time.perf_counter()
            migration,_,migration_stats=solve_experimental(raw,settings,waits,a.cores,12,0,BASELINE_FEATURES,evaluator_backend='counter')
            migration_seconds=time.perf_counter()-t
        plan,result,stats=solve(raw,settings,delay,provenance,a.cores,migration)
        assert stats['slots']==12 and stats['replay_equal']
    a.output.mkdir(parents=True)
    write_json(a.output/f'{a.graph.stem}_multicore_res.json',plan)
    write_json(a.output/'search.json',stats)
    if migration is not None:write_json(a.output/'migration_plan.json',migration)
    if migration_stats is not None:write_json(a.output/'migration_search.json',migration_stats)
    with gzip.open(a.output/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
    write_json(a.output/'run.json',dict(problem=2,algorithm=arm,cores=a.cores,makespan=result['makespan'],
               speedup=reference['makespan']/result['makespan'],added_copy_bytes=result['data_movement_bytes']['added_copy_bytes'],
               input_sha256=sha(a.graph.read_bytes()),solver_sha256=sha(Path(__file__).with_name('q2_reserve_fast.py').read_bytes()),
               migration_sha256=sha(a.migration.read_bytes()) if a.migration else None,provenance=provenance,
               migration_source='imported' if a.migration else 'generated_Q1_12_slots' if a.cores>1 else 'not_applicable',
               migration_generation_seconds=migration_seconds,
               elapsed_seconds=time.perf_counter()-start,timing_scope='includes fresh fixed reference, B search, final replay and output; includes seed generation only when --migration omitted'))
    print(result['makespan'])


if __name__=='__main__':main()
