"""Fresh-process, graph-only timing audit; never replaces frozen warm results.

Cold means no saved plans or solver caches. OS page caches are not flushed.
Q2 inherits freshly computed Q1, Q3 freshly computed Q2 (no historical anchor).
Elapsed cumulative prerequisites are reported, not hidden behind a 590s search.
"""
import argparse,concurrent.futures,json,os,platform,signal,subprocess,sys,time
from pathlib import Path
from q23_completion_shard import save
from q23_delivery_complete import read,sha

def audit(root,n,k,q1_final_check_backend='official'):
    out=root/f'case_{n:03}'/str(k);out.mkdir(parents=True,exist_ok=False)
    graph=Path(f'数据/processed/q1/data/case_{n:03}.json');rows=[];begin=time.monotonic()
    for q in (1,2,3):
        target=out/f'q{q}'
        if q==1:cmd=[sys.executable,'程序/q1_submit.py',str(graph),'-n',str(k),'--output',str(target),'--verify-final','--final-check-backend',q1_final_check_backend]
        else:
            prev=out/f'q{q-1}'/f'case_{n:03}_multicore_res.json'
            if not prev.exists():break
            cmd=[sys.executable,'程序/q23_submit_current.py',str(graph),'--problem',str(q),'-n',str(k),'--output',str(target),'--migration' if q==2 else '--seed-plan',str(prev)]
        t=time.monotonic();kw={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
        with (out/f'q{q}.log').open('wb') as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,**kw);timeout=False
            try:p.wait(timeout=2400 if q==1 else 650)
            except subprocess.TimeoutExpired:
                timeout=True
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                else:os.killpg(p.pid,signal.SIGKILL)
                p.wait()
        elapsed=time.monotonic()-t;cumulative=time.monotonic()-begin
        plan=target/f'case_{n:03}_multicore_res.json'
        row=dict(problem=q,case=n,cores=k,command=cmd,returncode=p.returncode,timeout=timeout,standalone_stage_seconds=elapsed,graph_only_cumulative_seconds=cumulative,within_600_seconds=cumulative<=600,verified=p.returncode==0 and plan.exists(),host=platform.node(),final_check_backend=q1_final_check_backend if q==1 else 'official',original_official_replayed=q!=1 or q1_final_check_backend=='official')
        if row['verified']:row['plan_sha256']=sha(plan)
        rows.append(row);save(out/'timing.json',dict(input_sha256=sha(graph),rows=rows,scope='cold graph-only chain; no historical plans; not frozen-score reproduction; OS page cache not flushed'))
        if not row['verified']:break
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--cases',nargs='+',type=int,default=[1,14,48,67,72,76]);p.add_argument('--cores',type=int,default=5);p.add_argument('--workers',type=int,default=2);p.add_argument('--q1-final-check-backend',choices=['official','counter'],default='official');a=p.parse_args()
    a.root.mkdir(parents=True,exist_ok=False)
    save(a.root/'contract.json',dict(cases=a.cases,cores=a.cores,workers=a.workers,q1_final_check_backend=a.q1_final_check_backend,selection='predeclared representative, dependency-heavy and largest input graphs; not all-100 cold coverage',source_sha256={x.name:sha(x) for x in Path('程序').glob('*.py')}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        fs=[ex.submit(audit,a.root,n,a.cores,a.q1_final_check_backend) for n in a.cases]
        for f in concurrent.futures.as_completed(fs):print(json.dumps(f.result()),flush=True)
    save(a.root/'complete.json',dict(completed=True,case_count=len(a.cases),full100_cold_timing=False))
