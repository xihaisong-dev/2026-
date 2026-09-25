"""Frozen full100 campaign: unique jobs, exact score provenance, no oracle merge."""
import argparse,csv,gzip,json,os,signal,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from q1_io import ROOT,PROCESSED,verify,sha,write_json
from q1_timed_portfolio import atomic_json

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def job_id(j):return f"case_{j['case']:03}_{j['cores']}cores_{j['method']}"

def freeze(out,methods,seconds,cores):
    manifest=verify();out.mkdir(parents=True,exist_ok=False)
    base=ROOT/'图表/runs/20260924-A-q1-event-ranking-full100'
    with (base/'all_case_results.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    baseline={f"{r['case']}_{r['cores']}":{k:int(r[k]) for k in ['single','makespan','added_copy_bytes']} for r in rows}
    assert len(baseline)==400 and set(baseline)=={f'case_{c:03}_{k}' for c in range(1,101) for k in range(2,6)}
    sources={p.name:sha(p.read_bytes()) for p in list((ROOT/'程序').glob('q1_*.py'))+[ROOT/'程序/q2_resources.py']}
    cases=sorted(range(1,101),key=lambda c:-(PROCESSED/f'data/case_{c:03}.json').stat().st_size)
    jobs=[dict(case=c,cores=k,method=m) for c in cases for k in cores for m in (methods if (c+k)%2 else methods[::-1])]
    write_json(out/'contract.json',dict(version=1,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources=sources,manifest_sha256=sha((PROCESSED/'manifest.json').read_bytes()),inputs=manifest['files'],baseline=baseline,
        methods=methods,cores=cores,seconds=seconds,seed=0,jobs=jobs,expected=len(jobs),single_reference_count=100,
        scope='Full100 regression for declared cores; fixed existing whole-graph single references; no per-case best-of-methods score',
        timing='Wall limit includes bootstrap/search/final original replay; excludes one-time fixed single-reference generation and campaign management',
        comparison='Existing adopted baseline has 12 search scores; comparison is result quality, not equal-time causal attribution. Both new methods, if selected, share one time cap.'))
    print(json.dumps(dict(frozen=len(jobs),methods=methods,seconds=seconds)))

def check(out):
    c=read(out/'contract.json')
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h,n
    assert sha((PROCESSED/'manifest.json').read_bytes())==c['manifest_sha256'];verify()
    return c

def run_job(out,c,j):
    name=job_id(j);folder=out/'jobs'/name;folder.parent.mkdir(exist_ok=True)
    row_path=out/'rows'/(name+'.json');row_path.parent.mkdir(exist_ok=True)
    if row_path.exists():return read(row_path)
    if folder.exists():
        row=dict(**j,status='incomplete_previous_attempt',valid=False)
        atomic_json(row_path,row);return row
    command=[sys.executable,str(ROOT/'程序/q1_staged_portfolio.py'),str(PROCESSED/f"data/case_{j['case']:03}.json"),'-n',str(j['cores']),
        '--seconds',str(c['seconds']),'--seed',str(c['seed']),'--output',str(folder)]
    if j['method']=='reuse_stage':command+=['--no-structure','--no-timeline']
    t=time.monotonic();timed_out=False
    with (out/'rows'/(name+'.log')).open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
        try:code=proc.wait(timeout=c['seconds']+45)
        except subprocess.TimeoutExpired:
            timed_out=True
            if os.name!='nt':os.killpg(proc.pid,signal.SIGKILL)
            else:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=log,stderr=log)
            code=proc.wait()
    row=dict(**j,status='failed',valid=False,exitcode=code,supervisor_timeout=timed_out,total_wall_seconds=time.monotonic()-t)
    if (folder/'run.json').exists():
        r=read(folder/'run.json');row.update(solver_wall_seconds=r['wall_seconds'],within_limit=r['within_limit'])
        if code==0 and r['complete'] and r['within_limit'] and not r.get('worker_error'):
            selected=folder/r['selected']['folder'];p=selected/'plan.json'
            exported=folder/f"case_{j['case']:03}_multicore_res.json";assert read(exported)==read(p)
            with gzip.open(selected/'evaluation.json.gz','rt',encoding='utf-8') as f:e=json.load(f)
            assert e['makespan']==r['selected']['makespan'] and e['num_cores']==j['cores']
            b=c['baseline'][f"case_{j['case']:03}_{j['cores']}"]
            row.update(status='complete',valid=True,makespan=e['makespan'],single=b['single'],speedup=b['single']/e['makespan'],
                added_copy_bytes=e['data_movement_bytes']['added_copy_bytes'],baseline_makespan=b['makespan'],baseline_added_copy_bytes=b['added_copy_bytes'],
                plan_sha256=sha(p.read_bytes()),evaluation_sha256=sha((selected/'evaluation.json.gz').read_bytes()),selected_folder=r['selected']['folder'],phases=r['phases'])
    atomic_json(row_path,row);return row

def report(out):
    c=read(out/'contract.json');rows=[read(p) for p in sorted((out/'rows').glob('*.json'))] if (out/'rows').exists() else []
    ids=[job_id(r) for r in rows];assert len(ids)==len(set(ids))
    assert set(ids)<={job_id(j) for j in c['jobs']}
    summary=dict(expected=c['expected'],finished=len(rows),valid=sum(r['valid'] for r in rows),failed=[r for r in rows if not r['valid']],complete=False,methods={})
    for method in c['methods']:
        points=[]
        for k in c['cores']:
            selected=[r for r in rows if r['method']==method and r['cores']==k and r['valid']]
            p=dict(cores=k,count=len(selected),complete=len(selected)==100)
            if selected:
                p.update(mean_speedup=sum(r['speedup'] for r in selected)/len(selected),total_cycles=sum(r['makespan'] for r in selected),
                    total_added_bytes=sum(r['added_copy_bytes'] for r in selected),wins=sum(r['makespan']<r['baseline_makespan'] for r in selected),
                    ties=sum(r['makespan']==r['baseline_makespan'] for r in selected),losses=sum(r['makespan']>r['baseline_makespan'] for r in selected),
                    max_solver_seconds=max(r['solver_wall_seconds'] for r in selected))
            points.append(p)
        summary['methods'][method]=points
    summary['complete']=len(rows)==c['expected'] and not summary['failed']
    atomic_json(out/'summary.json',summary)
    atomic_json(out/'pending.json',[j for j in c['jobs'] if job_id(j) not in ids])
    return summary

def launch(out,workers):
    from q2_resources import snapshot
    c=check(out);out.mkdir(exist_ok=True);lock=out/'launcher.lock'
    # Never run overlapping coordinators or silently overwrite a prior attempt.
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        write_json(out/'execution.json',dict(pid=os.getpid(),workers=workers,resources=snapshot(),python=sys.version,started=time.time()))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending=[j for j in c['jobs'] if not (out/'rows'/(job_id(j)+'.json')).exists()]
            futures=[pool.submit(run_job,out,c,j) for j in pending]
            for f in as_completed(futures):
                row=f.result();s=report(out);print(json.dumps(dict(job=job_id(row),valid=row['valid'],finished=s['finished'],expected=s['expected'])),flush=True)
        print(json.dumps(report(out)),flush=True)
    finally:lock.unlink()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','check','launch','report']);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--methods',nargs='+',choices=['full','reuse_stage'],default=['full']);ap.add_argument('--seconds',type=int,default=590);ap.add_argument('--workers',type=int,default=16)
    ap.add_argument('--cores',nargs='+',type=int,choices=range(2,6),default=[2,3,4,5])
    a=ap.parse_args()
    if not 20<=a.seconds<=600 or a.workers<1 or len(a.methods)!=len(set(a.methods)):ap.error('invalid limits or duplicate methods')
    if a.action=='freeze':freeze(a.output,a.methods,a.seconds,a.cores)
    elif a.action=='check':check(a.output);print('Source, data and configuration hashes verified')
    elif a.action=='launch':launch(a.output,a.workers)
    else:print(json.dumps(report(a.output),ensure_ascii=False))

if __name__=='__main__':main()
