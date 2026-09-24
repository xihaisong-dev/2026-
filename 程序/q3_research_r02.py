"""New held-out cases, equal candidate caps, untouched 500-plan baseline."""
import argparse,json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_solver import SceneBGraph
from q2_evaluator import key
from q3_solver import load,evaluate,audit
from q3_run import dump_gz
from q3_cache_search import candidates

DISCOVERY=[(5,5),(12,5),(67,2),(84,2),(92,3),(72,4)]
VALIDATION=[(7,5),(23,3),(38,4),(61,2),(76,5),(99,4)]
FAMILIES=['control','window','joint']

def job(args):
    case,n,family,baseline,out,budget=args
    folder=Path(out)/f'case_{case:03}/{n}/{family}';folder.mkdir(parents=True,exist_ok=False)
    src=Path(baseline)/f'case_{case:03}/{n}'
    plan=json.loads((src/f'case_{case:03}_multicore_res.json').read_text(encoding='utf-8'))
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'))
    s,d,c,_=load();t=time.perf_counter();anchor=evaluate(raw,plan,s,d,c)
    assert anchor['makespan']==json.loads((src/'metrics.json').read_text())['selected_l2']
    def obj(r):return r['makespan'],r['data_movement_bytes']['added_copy_bytes']
    best=plan;result=anchor;g=SceneBGraph(raw,s,d);rows=[]
    proposals,diagnostic=candidates(g,plan,anchor,family,budget,s,d)
    write_json(folder/'diagnostic.json',diagnostic)
    for item in proposals:
        try:
            r=evaluate(raw,item['plan'],s,d,c);accept=obj(r)<obj(result)
            if accept:best,result=item['plan'],r
            rows.append(dict(move=item['move'],makespan=r['makespan'],added_bytes=obj(r)[1],hit_rate=r['cache_stats']['hit_rate'],accepted=accept))
        except (RuntimeError,ValueError) as exc:rows.append(dict(move=item['move'],error=str(exc)))
    replay=evaluate(raw,best,s,d,c);assert replay==result
    checks=audit(raw,best,replay,s,d)
    write_json(folder/'plan.json',best);dump_gz(folder/'result.json.gz',replay)
    write_json(folder/'search.json',dict(evaluations=rows,checks=checks,replay_equal=True))
    row=dict(case=case,cores=n,family=family,baseline=anchor['makespan'],makespan=replay['makespan'],ratio=anchor['makespan']/replay['makespan'],hit_rate=replay['cache_stats']['hit_rate'],added_bytes=obj(replay)[1],candidate_calls=len(rows),invalid=sum('error' in r for r in rows),seconds=time.perf_counter()-t,plan_sha256=key(best))
    write_json(folder/'metrics.json',row);return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=12);p.add_argument('--budget',type=int,default=16);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    hashes={str(p.relative_to(a.baseline)):sha(p.read_bytes()) for p in a.baseline.rglob('*') if p.is_file() and (p.name=='metrics.json' or p.name.endswith('_multicore_res.json'))};assert len(hashes)==1000
    write_json(a.output/'contract.json',dict(discovery=DISCOVERY,validation=VALIDATION,families=FAMILIES,budget=a.budget,workers=a.workers,baseline_hashes=hashes,source_hashes={x:sha((ROOT/'程序'/x).read_bytes()) for x in ['q3_cache_search.py','q3_research_r02.py','q3_explore.py','q2_bottleneck_j.py']},promotion='New family must have >=3 discovery wins with mean ratio>=1.005, >=3 validation wins with mean ratio>=1.002, and validation mean ratio greater than control; every audit passes. Otherwise no full expansion.',formal_stage='NOT_RUN'))
    rows=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(job,(i,n,f,str(a.baseline),str(a.output),a.budget)):(i,n,f) for i,n in DISCOVERY+VALIDATION for f in FAMILIES}
        for f in as_completed(fs):
            try:row=f.result();rows.append(row);print(json.dumps(row),flush=True)
            except Exception as exc:errors.append(dict(job=fs[f],error=repr(exc)));print(errors[-1],flush=True)
            write_json(a.output/'progress.json',rows);write_json(a.output/'errors.json',errors)
    assert all(sha((a.baseline/p).read_bytes())==h for p,h in hashes.items())
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),errors=errors,baseline_unchanged=True))
    if errors:raise RuntimeError(errors)

if __name__=='__main__':main()
