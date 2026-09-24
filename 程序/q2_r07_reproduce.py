"""Replay selected official cases using the current submission CLI; no stored scores."""
import argparse,concurrent.futures,json,subprocess,sys
from pathlib import Path
from q1_io import ROOT,PROCESSED,write_json
from q2_resources import snapshot

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=int,nargs='+',default=list(range(1,101)))
    p.add_argument('--cores',type=int,nargs='+',default=[1,2,3,4,5])
    p.add_argument('--workers',type=int,default=1);p.add_argument('--output',type=Path,required=True);p.add_argument('--cold',action='store_true')
    a=p.parse_args();assert all(1<=i<=100 for i in a.cases) and all(1<=k<=5 for k in a.cores)
    assert a.workers>=1 and not a.output.exists();resources=snapshot()
    if a.workers>1 and a.workers>resources['recommended_workers']:raise ValueError('Insufficient current resource margin for requested parallelism')
    a.output.mkdir(parents=True);write_json(a.output/'execution.json',dict(resources=resources,workers=a.workers,cases=a.cases,cores=a.cores,cold=a.cold))
    def one(pair):
        i,k=pair;out=a.output/f'case_{i:03}/{k}';out.parent.mkdir(exist_ok=True)
        cmd=[sys.executable,str(ROOT/'程序/q2_current_submit.py'),str(PROCESSED/f'data/case_{i:03}.json'),'-n',str(k),'--output',str(out)]
        if k>1 and not a.cold:cmd+=['--migration',str(ROOT/f'图表/runs/20260924-A-q1-delivery-r02/solutions/{k}cores/case_{i:03}_multicore_res.json')]
        result=subprocess.run(cmd,capture_output=True)
        (out.parent/f'{k}.log.txt').write_bytes(result.stdout+result.stderr)
        return dict(case=i,cores=k,returncode=result.returncode)
    jobs=[(i,k) for i in sorted(set(a.cases)) for k in sorted(set(a.cores))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(one,jobs))
    write_json(a.output/'completion.json',dict(jobs=results,complete=all(r['returncode']==0 for r in results)))
    if any(r['returncode'] for r in results):raise RuntimeError('Some cases failed; retained output and logs')
    print(json.dumps(dict(completed=len(results))))

if __name__=='__main__':main()
