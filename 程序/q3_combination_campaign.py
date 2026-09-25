"""Paired Q3 pilot -> frozen full100 five-core combined rule; no casewise oracle."""
import argparse,csv,gzip,json,os,sys,time,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_timed_portfolio import atomic
from q2_full_timed import bounded
from q3_solver import load,evaluate,audit
from q2_evaluator import evaluate as no_l2

SEEDS=Path('图表/runs/20260925-A-q2-new-seeds/5cores')
ANCHORS=Path('图表/runs/20260924-A-q3-full-r02')
PILOT=[5,32,39,44,46,48,64,71,88]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def jid(j):return f"case_{j['case']:03}_{j['arm']}"

def freeze(out):
    verify();s,d,c,p=load();seeds=read(ROOT/SEEDS/'manifest.json')
    with (ROOT/'图表/runs/20260924-A-q3-delivery-r03/pairs.csv').open(encoding='utf-8-sig') as f:
        old={r['case']:dict(makespan=int(r['selected_l2']),added=int(r['selected_l2_added'])) for r in csv.DictReader(f) if r['cores']=='5'}
    paths={}
    for i in range(1,101):
        for f in [PROCESSED/f'data/case_{i:03}.json',ROOT/SEEDS/f'case_{i:03}_multicore_res.json',ROOT/ANCHORS/f'case_{i:03}/5/case_{i:03}_multicore_res.json']:
            paths[f.relative_to(ROOT).as_posix()]=sha(f.read_bytes())
    out.mkdir(parents=True,exist_ok=False)
    atomic(out/'contract.json',dict(problem=3,cores=5,seconds=590,seed=0,max_proposals=96,pilot=PILOT,
        settings=s,delay=d,cache=c,provenance=p,inputs=paths,baseline=old,seeds=seeds,
        sources={f.relative_to(ROOT).as_posix():sha(f.read_bytes()) for f in (ROOT/'程序').glob('q*.py')},
        jobs=[dict(case=i,arm='combined') for i in range(1,101)]+[dict(case=i,arm='local') for i in PILOT],
        expected=109,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        gate='All pilot results valid and combined pilot arithmetic mean T1/T_L2 >= local; otherwise do not launch remaining91.',
        timing='590s warm solve includes original Q3 scores/FIFO audits/checkpoints. Precomputed Q2/Q3 seeds, fixed T1, independent same-plan L2/no-L2 audit excluded.',
        metrics='fixed T1/selected L2, latest Q2 noL2/seed L2, selected noL2/selected L2, seed L2/selected L2; all arithmetic means separately; no oracle merge'))

def check(out):
    c=read(out/'contract.json');verify()
    for p,h in {**c['sources'],**c['inputs']}.items():assert sha((ROOT/p).read_bytes())==h,p
    return c

def validate(folder,i):
    s,d,c,_=load();q=read(folder/'summary.json');assert q['status']=='ok' and not q['worker_error'] and q['seconds']<=600
    raw=read(PROCESSED/f'data/case_{i:03}.json');plan=read(folder/q['plan'])
    with gzip.open(folder/q['evaluation'],'rt',encoding='utf-8') as f:saved=json.load(f)
    started=time.monotonic();r=evaluate(raw,plan,s,d,c);assert json.loads(json.dumps(r))==saved
    checks=audit(raw,plan,r,s,d)
    seed=read(ROOT/SEEDS/f'case_{i:03}_multicore_res.json');b=no_l2(raw,seed,s,d)
    assert b['makespan']==read(ROOT/SEEDS/'manifest.json')[f'case_{i:03}_multicore_res.json']['makespan']
    fixed=evaluate(raw,seed,s,d,c);selected_b=no_l2(raw,plan,s,d)
    assert selected_b['data_movement_bytes']==r['data_movement_bytes']
    for name,value in [('seed_no_l2',b),('seed_l2',fixed),('selected_no_l2',selected_b)]:
        with gzip.open(folder/(name+'.json.gz'),'wt',encoding='utf-8') as f:json.dump(value,f)
    atomic(folder/'audit.json',dict(equal=True,seconds=time.monotonic()-started,checks=checks,
        seed_no_l2=b['makespan'],seed_l2=fixed['makespan'],selected_no_l2=selected_b['makespan'],selected_l2=r['makespan'],
        hit_rate=r['cache_stats']['hit_rate'],physical_ddr_bytes=checks['cache']['physical_ddr_bytes_derived'],
        plan_file_sha256=sha((folder/q['plan']).read_bytes()),evaluation_sha256=sha((folder/q['evaluation']).read_bytes())))

def job(out,c,j):
    name=jid(j);folder=out/'jobs'/name;rp=out/'rows'/(name+'.json');log=out/'rows'/(name+'.log')
    if rp.exists():
        row=read(rp)
        if row['valid']:
            q=read(folder/'summary.json')
            assert sha((folder/q['plan']).read_bytes())==row['plan_file_sha256']
            assert sha((folder/q['evaluation']).read_bytes())==row['evaluation_sha256']
        return row
    i=j['case'];code=0
    if not folder.exists():
        cmd=[sys.executable,str(ROOT/'程序/q3_timed_combination.py'),str(PROCESSED/f'data/case_{i:03}.json'),
            '--seed-plan',str(ROOT/SEEDS/f'case_{i:03}_multicore_res.json'),
            '--anchor',str(ROOT/ANCHORS/f'case_{i:03}/5/case_{i:03}_multicore_res.json'),
            '--output',str(folder),'--arm',j['arm'],'--seconds',str(c['seconds']),'--seed',str(c['seed']),
            '--max-proposals',str(c['max_proposals'])]
        code,_=bounded(cmd,log,620)
    row=dict(**j,valid=False,status='incomplete',exitcode=code)
    if (folder/'summary.json').exists():
        q=read(folder/'summary.json');row.update(solve_seconds=q['seconds'],deadline_stop=q['deadline_stop'])
        if q['status']=='ok' and not q['worker_error'] and q['seconds']<=600 and code==0:
            if not (folder/'audit.json').exists():
                code,_=bounded([sys.executable,str(Path(__file__).resolve()),'validate','--output',str(folder),'--case',str(i)],log,600)
            if code==0 and (folder/'audit.json').exists():
                a=read(folder/'audit.json');single=c['seeds'][f'case_{i:03}_multicore_res.json']['single']
                row.update(a,valid=True,status='complete',single=single,speedup=single/a['selected_l2'],
                    hardware_ratio=a['seed_no_l2']/a['seed_l2'],same_plan_cache_ratio=a['selected_no_l2']/a['selected_l2'],
                    search_ratio=a['seed_l2']/a['selected_l2'],combined_ratio=a['seed_no_l2']/a['selected_l2'],
                    added=q['added_copy_bytes'],baseline=c['baseline'][str(i)]['makespan'])
    atomic(rp,row);return row

def report(out):
    c=read(out/'contract.json');rs=[read(p) for p in (out/'rows').glob('*.json')]
    summary=dict(finished=len(rs),expected=109,failed=[jid(r) for r in rs if not r['valid']],arms={})
    for arm in ['combined','local']:
        xs=[r for r in rs if r['arm']==arm and r['valid']];d=dict(count=len(xs),complete=len(xs)==(100 if arm=='combined' else len(PILOT)))
        if xs:
            d.update({f'mean_{m}':sum(r[m] for r in xs)/len(xs) for m in ['speedup','hardware_ratio','same_plan_cache_ratio','search_ratio','combined_ratio']})
            d.update(total_cycles=sum(r['selected_l2'] for r in xs),total_added=sum(r['added'] for r in xs),
                wins=sum(r['selected_l2']<r['baseline'] for r in xs),ties=sum(r['selected_l2']==r['baseline'] for r in xs),
                losses=sum(r['selected_l2']>r['baseline'] for r in xs))
        summary['arms'][arm]=d
    atomic(out/'summary.json',summary);return summary

def launch(out,workers):
    from q2_resources import snapshot
    c=check(out);lock=out/'launcher.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        for name in ['jobs','rows']:(out/name).mkdir(exist_ok=True)
        atomic(out/'execution.json',dict(pid=os.getpid(),workers=workers,started=time.time(),resources=snapshot()))
        def batch(js,n):
            with ThreadPoolExecutor(max_workers=n) as pool:
                for future in as_completed([pool.submit(job,out,c,j) for j in js]):
                    r=future.result();state=report(out);print(json.dumps(dict(job=jid(r),valid=r['valid'],finished=state['finished'])),flush=True)
        pilot=[dict(case=i,arm=a) for i in PILOT for a in (['local','combined'] if i%2 else ['combined','local'])]
        batch(pilot,min(8,workers))
        rows=[read(out/'rows'/(jid(j)+'.json')) for j in pilot]
        valid=all(r['valid'] and r['selected_l2']<=r['baseline'] for r in rows)
        means={a:sum(r.get('speedup',0) for r in rows if r['arm']==a)/len(PILOT) for a in ['local','combined']}
        passed=valid and means['combined']>=means['local']
        atomic(out/'pilot_gate.json',dict(passed=passed,all_valid=valid,means=means))
        if not passed:raise RuntimeError('Pilot gate failed; remaining91 not launched')
        order=sorted([i for i in range(1,101) if i not in PILOT],key=lambda i:-(PROCESSED/f'data/case_{i:03}.json').stat().st_size)
        batch([dict(case=i,arm='combined') for i in order],workers)
    finally:lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','check','launch','report','validate'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--case',type=int)
    a=p.parse_args();a.output=a.output.resolve()
    if a.action=='freeze':freeze(a.output)
    elif a.action=='check':check(a.output);print('hashes verified')
    elif a.action=='launch':launch(a.output,a.workers)
    elif a.action=='validate':validate(a.output,a.case)
    else:print(json.dumps(report(a.output)))
