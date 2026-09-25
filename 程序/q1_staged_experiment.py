"""Predeclared equal-wall-budget ablation; no best-of-methods official score."""
import argparse,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from q1_io import ROOT,write_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',type=int,required=True);ap.add_argument('--cores',nargs='+',type=int,default=[5]);ap.add_argument('--seconds',type=float,default=60)
    ap.add_argument('--workers',type=int,default=2);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    methods={'previous':('q1_timed_portfolio.py',[]),'reuse_stage':('q1_staged_portfolio.py',['--no-structure','--no-timeline']),
        'structure':('q1_staged_portfolio.py',['--no-timeline']),'full':('q1_staged_portfolio.py',[])}
    write_json(a.output/'protocol.json',dict(cases=a.cases,cores=a.cores,seconds=a.seconds,workers=a.workers,methods=methods,seed=0,
        role='Case list fixed before this batch; no rule tuning after outcomes within this batch',unit='case x cores; all methods cold start; time cap includes final official replay'))
    def one(c,k,m):
        folder=a.output/f'case_{c:03}_{k}cores_{m}';script,extra=methods[m]
        cmd=[sys.executable,str(ROOT/'程序'/script),str(ROOT/f'数据/processed/q1/data/case_{c:03}.json'),'-n',str(k),'--seconds',str(a.seconds),'--output',str(folder)]+extra
        with (a.output/f'case_{c:03}_{k}_{m}.log').open('w',encoding='utf-8') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
        status=json.loads((folder/'run.json').read_text(encoding='utf-8'))
        return dict(case=c,cores=k,method=m,exitcode=r.returncode,run=status)
    rows=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(one,c,k,m) for c in a.cases for k in a.cores for m in methods]
        for f in as_completed(futures):
            row=f.result();rows.append(row);write_json(a.output/'progress.json',rows)
            print(json.dumps(dict(case=row['case'],method=row['method'],exitcode=row['exitcode'],selected=row['run'].get('selected'),seconds=row['run']['wall_seconds'])),flush=True)
    write_json(a.output/'summary.json',rows)

if __name__=='__main__':main()
