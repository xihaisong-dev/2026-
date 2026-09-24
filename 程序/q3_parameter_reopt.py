"""Diagnostic fixed-plan vs reoptimized-plan C x B study; not official scores."""
import argparse,json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_solver import SceneBGraph
from q3_solver import load,evaluate,audit
from q3_cache_search import candidates
from q3_run import dump_gz

def job(args):
    case,n,cap,bw,baseline,out=args;t=time.perf_counter()
    folder=Path(out)/f'case_{case:03}/{cap}_{bw}';folder.mkdir(parents=True,exist_ok=False)
    src=Path(baseline)/f'case_{case:03}/{n}'
    seed=json.loads((src/f'case_{case:03}_multicore_res.json').read_text(encoding='utf-8'))
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'))
    s,d,c,_=load();c=dict(c);c['cache_capacity_bytes']=cap;c['cache_bandwidth_bytes_per_cycle']=bw
    fixed=evaluate(raw,seed,s,d,c);best=seed;result=fixed
    proposals,diagnostic=candidates(SceneBGraph(raw,s,d),seed,fixed,'joint',8,s,d)
    def objective(r):return r['makespan'],r['data_movement_bytes']['added_copy_bytes']
    rows=[]
    for x in proposals:
        try:
            r=evaluate(raw,x['plan'],s,d,c);accepted=objective(r)<objective(result)
            if accepted:best,result=x['plan'],r
            rows.append(dict(move=x['move'],makespan=r['makespan'],accepted=accepted))
        except (RuntimeError,ValueError) as exc:rows.append(dict(move=x['move'],error=str(exc)))
    replay=evaluate(raw,best,s,d,c);assert replay==result
    checks=audit(raw,best,replay,s,d);audit(raw,seed,fixed,s,d)
    write_json(folder/'plan.json',best);dump_gz(folder/'fixed.json.gz',fixed);dump_gz(folder/'selected.json.gz',replay)
    write_json(folder/'search.json',dict(diagnostic=diagnostic,evaluations=rows,checks=checks,replay_equal=True))
    owners=lambda p:{k:i for i,q in enumerate(p['core_schedules']) for k in q}
    a,b=owners(seed),owners(best)
    row=dict(case=case,cores=n,capacity=cap,bandwidth=bw,fixed=fixed['makespan'],selected=replay['makespan'],ratio=fixed['makespan']/replay['makespan'],fixed_hit=fixed['cache_stats']['hit_rate'],selected_hit=replay['cache_stats']['hit_rate'],moved_groups=sum(a[k]!=b[k] for k in a),changed_core_orders=sum(x!=y for x,y in zip(seed['core_schedules'],best['core_schedules'])),candidate_calls=len(rows),seconds=time.perf_counter()-t)
    write_json(folder/'metrics.json',row);return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    write_json(a.output/'contract.json',dict(cases=[[5,5],[12,5]],capacities=[524288,1048576,2097152],bandwidths=[125,250,500],budget=8,scope='18 diagnostic runs on two development cases; fixed full-r02 seed vs joint reoptimization at each hardware configuration. Not a generalization test or replacement official result.',source_hashes={x:sha((ROOT/'程序'/x).read_bytes()) for x in ['q3_parameter_reopt.py','q3_cache_search.py']}))
    rows=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(job,(i,n,c,b,str(a.baseline),str(a.output))):(i,n,c,b) for i,n in [(5,5),(12,5)] for c in [524288,1048576,2097152] for b in [125,250,500]}
        for f in as_completed(fs):
            try:row=f.result();rows.append(row);print(json.dumps(row),flush=True)
            except Exception as exc:errors.append(dict(job=fs[f],error=repr(exc)))
            write_json(a.output/'progress.json',rows);write_json(a.output/'errors.json',errors)
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),errors=errors))
    if errors:raise RuntimeError(errors)

if __name__=='__main__':main()
