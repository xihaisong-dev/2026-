"""ASAP pilot: critical HOL insertion, root-preserving branch search, equal-cap control."""
import argparse,json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from q1_io import ROOT,PROCESSED,sha,write_json
from q3_solver import load
from q3_adaptive import solve as control_solve
from q3_asap import solve as asap_solve
def solve(raw,seed,s,d,c,mode,budget):
    return control_solve(raw,seed,s,d,c,"unclassified_iterative",budget) if mode=="control" else asap_solve(raw,seed,s,d,c,mode,budget)
from q3_run import dump_gz
DISCOVERY=[(5,5),(12,5),(58,2),(67,2)]
VALIDATION=[(16,5),(31,3),(49,4),(64,2),(87,5),(98,4)]
MODES=['single','beam','control']

def job(args):
    case,n,mode,baseline,out=args;t=time.perf_counter();folder=Path(out)/f'case_{case:03}/{n}/{mode}';folder.mkdir(parents=True,exist_ok=False)
    src=Path(baseline)/f'case_{case:03}/{n}';seed=json.loads((src/f'case_{case:03}_multicore_res.json').read_text(encoding='utf-8'))
    raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'));s,d,c,_=load()
    best,result,anchor,search=solve(raw,seed,s,d,c,mode,24)
    assert anchor['makespan']==json.loads((src/'metrics.json').read_text())['selected_l2']
    write_json(folder/'plan.json',best);write_json(folder/'search.json',search);dump_gz(folder/'result.json.gz',result)
    row=dict(case=case,cores=n,mode=mode,baseline=anchor['makespan'],makespan=result['makespan'],ratio=anchor['makespan']/result['makespan'],added_bytes=result['data_movement_bytes']['added_copy_bytes'],hit_rate=result['cache_stats']['hit_rate'],calls=len(search['evaluations']),diagnoses=len(search['rounds']),accepted_rounds=sum(x.get('accepted',False) for x in search['evaluations']),invalid=sum('error' in x for x in search['evaluations']),seconds=time.perf_counter()-t)
    write_json(folder/'metrics.json',row);return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=12);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    hashes={str(p.relative_to(a.baseline)):sha(p.read_bytes()) for p in a.baseline.rglob('*') if p.is_file() and (p.name=='metrics.json' or p.name.endswith('_multicore_res.json'))};assert len(hashes)==1000
    write_json(a.output/'contract.json',dict(discovery=DISCOVERY,validation=VALIDATION,modes=MODES,budget=24,batch=4,baseline_hashes=hashes,sources={x:sha((ROOT/'程序'/x).read_bytes()) for x in ['q3_asap.py','q3_asap_run.py','q3_adaptive.py','q3_cache_search_fast.py','q3_explore.py','q2_bottleneck_j.py']},promotion='Pilot only: no automatic full expansion. Beam needs >=3/6 validation makespan wins against baseline, mean reduction >=0.2%, >=2 wins against control and single, and better mean reduction than both; all audits pass. Retained historical best also reported. Equal maximum 24 unique candidates; actual calls and runtime reported; no padding when legal HOL menu exhausted.',scope='New algorithm validation cases, not unseen baseline data. Parameter studies retained unchanged. NOT formal stage approval.'))
    rows=[];errors=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(job,(i,n,m,str(a.baseline),str(a.output))):(i,n,m) for i,n in DISCOVERY+VALIDATION for m in MODES}
        for f in as_completed(fs):
            try:r=f.result();rows.append(r);print(json.dumps(r),flush=True)
            except Exception as exc:errors.append(dict(job=fs[f],error=repr(exc)));print(errors[-1],flush=True)
            write_json(a.output/'progress.json',rows);write_json(a.output/'errors.json',errors)
    assert all(sha((a.baseline/p).read_bytes())==h for p,h in hashes.items())
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),errors=errors,baseline_unchanged=True))
    if errors:raise RuntimeError(errors)

if __name__=='__main__':main()
