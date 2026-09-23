"""Run exact contraction acceleration and verify archived official trajectories."""
import argparse, gzip, json, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from q1_io import ROOT, write_json, sha, verify
from q1_memory_audit import context


def run(job):
    cores,root,previous,fast=job;raw,settings,waits=context('case_091')
    from q1_single_reference import reference
    from q1_experimental import solve_experimental
    from q1_ablation import CONFIGS
    prev=Path(previous)/f'case_091_{cores}cores_seed0_component_local_rank'
    prior= json.loads(gzip.decompress((prev/'evaluation.json.gz').read_bytes()))
    single=json.loads(gzip.decompress((ROOT/'references/case_091/single/evaluation.json.gz').read_bytes()))
    fixed=reference(raw,settings,waits,single);events=[]
    start=time.perf_counter()
    plan,result,stats=solve_experimental(raw,settings,waits,cores,12,0,CONFIGS['component_fast' if fast else 'component_local_rank'],single_reference=fixed,evaluator_backend='counter',on_evaluation=lambda r:events.append(dict(r)))
    seconds=time.perf_counter()-start
    old=json.loads((prev/'search.json').read_text())
    signature=lambda s:[(r['candidate'],r['makespan'],r['added_copy_bytes']) for r in s['evaluations']]
    checks=dict(plan=plan==json.loads((prev/'plan.json').read_text()),result=json.loads(json.dumps(result))==prior,trajectory=signature(stats)==signature(old))
    assert all(checks.values()),checks
    out=Path(root)/f"{cores}cores_{'fast' if fast else 'base'}";out.mkdir()
    write_json(out/'search.json',stats);write_json(out/'plan.json',plan)
    row=dict(cores=cores,fast=fast,seconds=seconds,checks=checks,full_score_calls=stats['official_calls'],reference_hits=stats['cache_hits'],historical_solve_seconds=json.loads((prev/'row.json').read_text())['solve_seconds'],archived_official_result_sha256=sha((prev/'evaluation.json.gz').read_bytes()))
    write_json(out/'row.json',row);return row


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--previous',required=True);ap.add_argument('--paired',action='store_true');a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);verify()
    write_json(a.output/'sources.json',{p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')})
    if a.paired:
        # Sequential same host, same worker count. Keep each result immediately.
        rows=[]
        for fast in [False,True]:
            rows.append(run((5,str(a.output),a.previous,fast)));write_json(a.output/'summary.json',dict(completed=len(rows)==2,rows=rows))
    else:
        with ProcessPoolExecutor(max_workers=4) as pool:rows=list(pool.map(run,[(c,str(a.output),a.previous,True) for c in range(2,6)]))
        write_json(a.output/'summary.json',dict(completed=True,rows=rows))


if __name__=='__main__':main()
