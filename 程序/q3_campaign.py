"""Resource-checked process batch; each job owns one fresh case/core directory."""
import argparse,concurrent.futures,json,platform,time
from pathlib import Path
from q1_io import ROOT,sha,write_json
from q2_resources import snapshot
from q3_solver import load
from q3_run import one


def job(args):
    c,n,out,budget=args
    s,d,cache,_=load()
    return one(c,n,Path(out)/f'case_{c:03}/{n}',s,d,cache,budget,'cache')


def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=1)
    p.add_argument('--budget',type=int,default=4);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cases',type=int,nargs='+',default=list(range(1,101)))
    p.add_argument('--cores',type=int,nargs='+',default=[1,2,3,4,5]);a=p.parse_args()
    resources=snapshot(worker_gib=1.5)
    if a.workers>1 and a.workers>resources['recommended_workers']:raise ValueError(resources)
    a.output.mkdir(parents=True,exist_ok=False);s,d,c,provenance=load()
    write_json(a.output/'contract.json',dict(cases=a.cases,cores=a.cores,budget=a.budget,mode='cache',
               settings=s,delay=d,cache=c,provenance=provenance,python=platform.python_version(),resources=resources,
               source_hashes={x.name:sha(x.read_bytes()) for x in (ROOT/'程序').glob('*.py')},workers=a.workers,
               seed_source='Q2 r07 c47a5986',stage_gate='NOT_RUN'))
    rows=[];errors=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(job,(i,n,str(a.output),a.budget)):(i,n) for i in a.cases for n in a.cores}
        for f in concurrent.futures.as_completed(futures):
            try:
                row=f.result();rows.append(row)
                print(json.dumps(dict(case=row['case'],cores=row['cores'],seconds=row['total_seconds'],completed=len(rows))),flush=True)
            except Exception as exc:errors.append(dict(pair=futures[f],error=repr(exc)))
            write_json(a.output/'progress.json',sorted(rows,key=lambda x:(x['case'],x['cores'])))
            write_json(a.output/'errors.json',errors)
    write_json(a.output/'completion.json',dict(complete=not errors,count=len(rows),errors=errors))
    if errors:raise RuntimeError(errors)


if __name__=='__main__':main()
