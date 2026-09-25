"""Frozen Q2 full100 five-core comparison with preflight and audited resume.

Full official acceptance occurs within solve time. An independent post-run replay
is an audit, separately timed and not hidden in the 590-second search allowance.
"""
import argparse,csv,gzip,json,os,signal,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_timed_portfolio import atomic

ARMS=['ordinary_extended','protected']
SEEDS=Path('图表/runs/20260924-A-q1-delivery-r02/solutions/5cores')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def jid(j):return f"case_{j['case']:03}_{j['arm']}"


def freeze(out):
    from q2_evaluator import load
    settings,delay,provenance=load()
    refs=read(ROOT/'图表/runs/20260924-A-q2-full-r05/contract.json')['fixed_references']
    with (ROOT/'图表/runs/20260924-A-q2-full-r07-shared-r08/pairs.csv').open(encoding='utf-8-sig') as f:
        baseline={str(int(r['case'])):dict(makespan=int(r['r07']),added_copy_bytes=int(r['r07_bytes']),
            single=int(refs[f"case_{int(r['case']):03}"])) for r in csv.DictReader(f) if r['cores']=='5'}
    assert set(baseline)==set(map(str,range(1,101)))
    files=list((ROOT/'程序').glob('q*.py'))
    manifest=verify();paths={}
    for i in range(1,101):
        for p in [PROCESSED/f'data/case_{i:03}.json',ROOT/SEEDS/f'case_{i:03}_multicore_res.json']:
            paths[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    cases=sorted(range(1,101),key=lambda i:-(PROCESSED/f'data/case_{i:03}.json').stat().st_size)
    jobs=[dict(case=i,arm=a) for i in cases for a in (ARMS if i%2 else ARMS[::-1])]
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'contract.json',dict(version=1,cores=5,cases=100,expected=200,arms=ARMS,seed=0,seconds=590,
        max_proposals=96,jobs=jobs,preflight_cases=[67,72],baseline=baseline,inputs=paths,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in files},
        manifest_sha256=sha((PROCESSED/'manifest.json').read_bytes()),settings=settings,delay=delay,provenance=provenance,
        timing='Warm shared Q1 seed; solve includes loading/generation/original official scoring/checkpoint. Fixed T1, seed generation and independent audit excluded and declared.',
        selection='Report each fixed arm over all100. Never select different arms post hoc per case. Failures prevent complete mean.',
        decision='Compare mean per-case speedup, total cycles, added bytes, wins/ties/losses, worst regression, solve/audit timing. No automatic replacement of formal results.',
        preflight='Both arms on 067/072 must be valid, solve<=600s, original independent replay identical. These frozen jobs are reused in the full200.'))


def check(out):
    c=read(out/'contract.json')
    for p,h in {**c['sources'],**c['inputs']}.items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('Frozen hash mismatch: '+p)
    assert sha((PROCESSED/'manifest.json').read_bytes())==c['manifest_sha256'];verify()
    return c


def validate(folder,case):
    from q2_evaluator import load,evaluate,key
    s=read(folder/'summary.json')
    if s['status']!='ok' or s['worker_error'] or s['seconds']>600:raise ValueError('Solver failed or exceeded 600s')
    pointer=read(folder/'verified.json');assert pointer['plan_sha256']==s['plan_sha256']
    plan=read(folder/pointer['plan']);assert key(plan)==s['plan_sha256']
    settings,delay,_=load();raw=read(PROCESSED/f'data/case_{case:03}.json')
    with gzip.open(folder/pointer['evaluation'],'rt',encoding='utf-8') as f:saved=json.load(f)
    started=time.monotonic();actual=evaluate(raw,plan,settings,delay)
    assert json.loads(json.dumps(actual))==saved
    assert actual['num_cores']==5 and actual['makespan']==s['makespan']
    atomic(folder/'audit.json',dict(equal=True,seconds=time.monotonic()-started,plan_sha256=sha((folder/pointer['plan']).read_bytes()),
        evaluation_sha256=sha((folder/pointer['evaluation']).read_bytes())))


def bounded(command,log,seconds):
    with log.open('a',encoding='utf-8') as f:
        p=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
        try:return p.wait(timeout=seconds),False
        except subprocess.TimeoutExpired:
            if os.name!='nt':os.killpg(p.pid,signal.SIGKILL)
            else:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=f,stderr=f)
            return p.wait(),True


def saved_row_valid(out,row):
    if not row['valid']:return True  # recorded failure stays visible; no silent retries
    folder=out/'jobs'/jid(row);s=read(folder/'summary.json');audit=read(folder/'audit.json')
    return (audit['equal'] and sha((folder/s['plan']).read_bytes())==row['plan_sha256'] and
            sha((folder/s['evaluation']).read_bytes())==row['evaluation_sha256'])


def run_job(out,c,j):
    name=jid(j);row_path=out/'rows'/(name+'.json');folder=out/'jobs'/name
    if row_path.exists():
        row=read(row_path)
        if not saved_row_valid(out,row):raise ValueError('Completed result corrupted: '+name)
        return row
    started=time.monotonic();log=out/'rows'/(name+'.log');code=0;timeout=False
    if not folder.exists():
        command=[sys.executable,str(ROOT/'程序/q2_timed_portfolio.py'),str(PROCESSED/f"data/case_{j['case']:03}.json"),
            '--output',str(folder),'--arm',j['arm'],'--cores','5','--seconds',str(c['seconds']),
            '--seed',str(c['seed']),'--max-proposals',str(c['max_proposals']),
            '--migration',str(ROOT/SEEDS/f"case_{j['case']:03}_multicore_res.json")]
        code,timeout=bounded(command,log,620)
    row=dict(**j,valid=False,status='failed',exitcode=code,supervisor_timeout=timeout)
    if (folder/'summary.json').exists():
        s=read(folder/'summary.json');row.update(solve_seconds=s['seconds'],deadline_stop=s['deadline_stop'])
        if s['status']=='ok' and not s['worker_error'] and s['seconds']<=600 and code==0:
            if not (folder/'audit.json').exists():
                ac,at=bounded([sys.executable,str(Path(__file__).resolve()),'validate','--output',str(folder),'--case',str(j['case'])],log,600)
            else:ac,at=0,False
            row.update(audit_exitcode=ac,audit_timeout=at)
            if ac==0 and (folder/'audit.json').exists():
                a=read(folder/'audit.json');b=c['baseline'][str(j['case'])]
                row.update(status='complete',valid=True,makespan=s['makespan'],added_copy_bytes=s['added_copy_bytes'],
                    single=b['single'],speedup=b['single']/s['makespan'],baseline_makespan=b['makespan'],
                    baseline_added_copy_bytes=b['added_copy_bytes'],audit_seconds=a['seconds'],
                    plan_sha256=a['plan_sha256'],evaluation_sha256=a['evaluation_sha256'])
    elif folder.exists():row['status']='incomplete_previous_attempt'
    row['total_job_seconds']=time.monotonic()-started;atomic(row_path,row);return row


def report(out):
    c=read(out/'contract.json');rows=[read(p) for p in (out/'rows').glob('*.json')]
    ids={jid(r) for r in rows};assert len(ids)==len(rows)
    assert ids<={jid(j) for j in c['jobs']}
    result=dict(expected=200,finished=len(rows),valid=sum(r['valid'] for r in rows),
        failed=[jid(r) for r in rows if not r['valid']],complete=len(rows)==200 and all(r['valid'] for r in rows),arms={})
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm and r['valid']]
        p=dict(count=len(rs),complete=len(rs)==100)
        if rs:p.update(mean_speedup=sum(r['speedup'] for r in rs)/len(rs),total_cycles=sum(r['makespan'] for r in rs),
            total_added_bytes=sum(r['added_copy_bytes'] for r in rs),wins=sum(r['makespan']<r['baseline_makespan'] for r in rs),
            ties=sum(r['makespan']==r['baseline_makespan'] for r in rs),losses=sum(r['makespan']>r['baseline_makespan'] for r in rs),
            worst_regression=max(r['makespan']/r['baseline_makespan']-1 for r in rs),max_solve_seconds=max(r['solve_seconds'] for r in rs))
        result['arms'][arm]=p
    pairs=[]
    by={(r['case'],r['arm']):r for r in rows if r['valid']}
    for i in range(1,101):
        if all((i,a) in by for a in ARMS):
            old,new=(by[i,a] for a in ARMS)
            pairs.append(dict(case=i,ordinary=old['makespan'],protected=new['makespan'],ratio=old['makespan']/new['makespan']))
    atomic(out/'pairs.json',pairs);atomic(out/'summary.json',result)
    atomic(out/'pending.json',[j for j in c['jobs'] if jid(j) not in ids]);return result


def launch(out,workers):
    from q2_resources import snapshot
    c=check(out);lock=out/'launcher.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        for name in ['jobs','rows']:(out/name).mkdir(exist_ok=True)
        atomic(out/'execution.json',dict(pid=os.getpid(),requested_workers=workers,started=time.time(),resources=snapshot(),python=sys.version))
        pre=[j for j in c['jobs'] if j['case'] in c['preflight_cases']]
        def batch(jobs,n):
            with ThreadPoolExecutor(max_workers=n) as pool:
                for f in as_completed([pool.submit(run_job,out,c,j) for j in jobs]):
                    r=f.result();s=report(out);print(json.dumps(dict(job=jid(r),valid=r['valid'],finished=s['finished'])),flush=True)
        batch(pre,min(4,workers))
        passed=all(read(out/'rows'/(jid(j)+'.json'))['valid'] for j in pre)
        atomic(out/'preflight.json',dict(passed=passed,jobs=pre,time=time.time()))
        if not passed:raise RuntimeError('Preflight failed; full batch NOT launched')
        resources=snapshot();actual=min(workers,max(1,resources['recommended_workers']))
        atomic(out/'full_launch.json',dict(workers=actual,time=time.time(),resources=resources))
        # Longest inputs first, paired arm order alternates by case. Existing
        # preflight results are validated/reused rather than computed twice.
        batch([j for j in c['jobs'] if j not in pre],actual)
        print(json.dumps(report(out)),flush=True)
    finally:lock.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','check','launch','report','validate'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--case',type=int)
    a=p.parse_args();a.output=a.output.resolve()
    if a.workers<1:p.error('positive workers required')
    if a.action=='freeze':freeze(a.output)
    elif a.action=='check':check(a.output);print('Frozen hashes match')
    elif a.action=='launch':launch(a.output,a.workers)
    elif a.action=='validate':validate(a.output,a.case)
    else:print(json.dumps(report(a.output),ensure_ascii=False))
