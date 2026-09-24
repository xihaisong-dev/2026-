"""Portable Q2 entry. Optional Q1 plan is replayed under B; no A score imported."""
import argparse,gzip,json,time
from pathlib import Path
from q1_io import PROCESSED,write_json,sha
from q2_evaluator import load,fixed_reference
from q2_current import solve
from q2_single_reference import fixed_reference_fast,BACKEND_ID


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,choices=range(1,6),required=True)
    ap.add_argument('--migration',type=Path);ap.add_argument('--config',type=Path,default=PROCESSED/'data/config.txt')
    ap.add_argument('--mode',choices=['base','ordinary','guided'],default='ordinary')
    ap.add_argument('--reference-backend',choices=['official','counter'],default='counter')
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    start=time.perf_counter();settings,delay,provenance=load(a.config)
    raw=json.loads(a.graph.read_text(encoding='utf-8-sig'))
    reference=(fixed_reference_fast if a.reference_backend=='counter' else fixed_reference)(raw,settings)
    if a.cores==1:
        from singlecore_evaluate import build_singlecore_plan
        plan=build_singlecore_plan(raw);result=reference;stats={'mode':'prescribed_fixed_singlecore_reference','speedup':1.}
    else:
        migration=json.loads(a.migration.read_text(encoding='utf-8-sig')) if a.migration else None
        plan,result,stats=solve(raw,settings,delay,provenance,a.cores,migration,a.mode)
        stats['speedup']=reference['makespan']/result['makespan']
    a.output.mkdir(parents=True,exist_ok=False)
    write_json(a.output/f'{a.graph.stem}_multicore_res.json',plan)
    write_json(a.output/'search.json',stats)
    with gzip.open(a.output/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
    write_json(a.output/'run.json',dict(problem=2,mode=stats['mode'],makespan=result['makespan'],speedup=stats['speedup'],
        input_sha256=sha(a.graph.read_bytes()),config_sha256=sha(a.config.read_bytes()),provenance=provenance,reference_backend=BACKEND_ID if a.reference_backend=='counter' else 'official',
        total_seconds=time.perf_counter()-start,migration_sha256=sha(a.migration.read_bytes()) if a.migration else None,
        source_sha256={p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('q2_*.py')}))
    print(result['makespan'],stats['speedup'])


if __name__=='__main__':main()
