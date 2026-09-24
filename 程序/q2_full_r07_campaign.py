"""Official100 r07 confirmation plus exact shared-menu audit and paired pilot."""
import argparse,concurrent.futures,csv,gzip,json,math,os,statistics,subprocess,sys,time
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load,key
from q2_reserve_fast import solve as fast
from q2_reserve_shared import solve as shared,menu
from q2_full_campaign import OUT as BASE,Q1,read
from q2_single_reference import fixed_reference_fast
from q2_resources import snapshot
from q2_physical import PhysicalScorer

OUT=ROOT/'图表/runs/20260924-A-q2-full-r07-shared-r08'
PILOT=[1,5,12,22,24,35,48,49,50,64,69,71,86,88]

def freeze():
    assert not OUT.exists();OUT.mkdir(parents=True)
    settings,delay,prov=load();b=read(BASE/'contract.json')
    write_json(OUT/'contract.json',dict(cases=list(range(1,101)),cores=[2,3,4,5],pilot=PILOT,budget=12,seed=0,
        settings=settings,delay=delay,provenance=prov,inputs=b['inputs'],plans=b['plans'],fixed_references=b['fixed_references'],
        sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')},
        baseline_contract_sha256=sha((BASE/'contract.json').read_bytes()),
        scope='Full official100 regression, not unseen validation. Frozen r07 fresh400 B solves; shared400 exact menu checks and fixed56 paired solves. No automatic default replacement.',
        timing='Compare fresh r07/shared only on fixed14 paired graphs; never compare wall times to historical r05. Candidate menu audit and physical capacity audit are outside search timer.'))

def run_case(i):
    c=read(OUT/'contract.json')
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h,n
    settings,delay,prov=load();assert (settings,delay,prov)==(c['settings'],c['delay'],c['provenance'])
    p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)];raw=read(p)
    dest=OUT/f'cases/case_{i:03}';assert not dest.exists();dest.mkdir(parents=True)
    t=time.perf_counter();ref=fixed_reference_fast(raw,settings);assert ref['makespan']==c['fixed_references'][f'case_{i:03}']
    write_json(dest/'single.json',dict(makespan=ref['makespan'],seconds=time.perf_counter()-t,backend='pinned_exact_counter',added_copy_bytes=ref['data_movement_bytes']['added_copy_bytes']))
    for k in c['cores']:
        p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';assert sha(p.read_bytes())==c['plans'][p.relative_to(ROOT).as_posix()];migration=read(p)
        arms=['fast','shared'] if i in PILOT else ['fast']
        if (i+k)%2:arms=arms[::-1]
        answers={}
        for arm in arms:
            plan,result,stats=(fast if arm=='fast' else shared)(raw,settings,delay,prov,k,migration)
            assert stats['slots']==12 and stats['replay_equal']
            row=dict(case=i,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],reference=ref['makespan'],speedup=ref['makespan']/result['makespan'],
                **{x:stats[x] for x in ['slots','official_calls','cache_hits','solve_seconds','replay_seconds','base_makespan']},candidate_seconds=stats['candidate_seconds'])
            folder=dest/str(k)/arm;folder.mkdir(parents=True);write_json(folder/'plan.json',plan);write_json(folder/'search.json',stats);write_json(folder/'row.json',row)
            with gzip.open(folder/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
            answers[arm]=(plan,result,stats)
        p,r,s=answers['fast'];metadata={};t=time.perf_counter();g,items=menu(raw,settings,delay,k,migration,metadata)
        assert [(name,key(plan)) for name,plan in items]==[(x['name'],x['plan_sha256']) for x in s['evaluations'][2:8]]
        check=dict(shared_menu_exact=True,menu_audit_seconds=time.perf_counter()-t)
        if 'shared' in answers:
            q,v,u=answers['shared'];assert p==q and r==v
            assert [(x['name'],x['plan_sha256'],x.get('makespan'),x.get('bytes'),x['cache_hit']) for x in s['evaluations']]==[(x['name'],x['plan_sha256'],x.get('makespan'),x.get('bytes'),x['cache_hit']) for x in u['evaluations']]
            check['shared_full_result_and_trajectory_exact']=True
        t=time.perf_counter();profiles=PhysicalScorer(raw,settings,delay).actual_lifetimes(p,r)
        check.update(global_capacity_pass=True,capacity_seconds=time.perf_counter()-t,peaks={str(c):v['peak_bytes'] for c,v in profiles.items()})
        write_json(dest/str(k)/'checks.json',check);print('DONE',i,k,flush=True)
    write_json(dest/'complete.json',dict(complete=True))

def launch(workers):
    r=snapshot(worker_gib=4.);assert workers<=r['recommended_workers'];assert not (OUT/'execution.json').exists();write_json(OUT/'execution.json',dict(resources=r,workers=workers))
    logs=OUT/'logs';logs.mkdir()
    ids=sorted(range(1,101),key=lambda i:-(PROCESSED/f'data/case_{i:03}.json').stat().st_size)
    def one(i):
        with (logs/f'case_{i:03}.txt').open('w',encoding='utf-8') as f:
            p=subprocess.run([sys.executable,__file__,'case','--case',str(i)],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
        return dict(case=i,returncode=p.returncode)
    done=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(one,i) for i in ids]
        for f in concurrent.futures.as_completed(jobs):
            done.append(f.result());write_json(OUT/'progress.json',dict(completed=len(done),failed=[x for x in done if x['returncode']],jobs=done));print(done[-1],'TOTAL',len(done),flush=True)
    assert all(x['returncode']==0 for x in done)

def report():
    c=read(OUT/'contract.json');rows=[];pairs=[];pilot=[];invalid=[]
    for i in c['cases']:
        assert read(OUT/f'cases/case_{i:03}/complete.json')['complete']
        for k in c['cores']:
            folder=OUT/f'cases/case_{i:03}/{k}';checks=read(folder/'checks.json');assert checks['shared_menu_exact'] and checks['global_capacity_pass']
            b=read(BASE/f'cases/case_{i:03}/{k}/routed/row.json');r=read(folder/'fast/row.json');rows.append(r)
            pairs.append(dict(case=i,cores=k,r05=b['makespan'],r07=r['makespan'],ratio=b['makespan']/r['makespan'],r05_bytes=b['bytes'],r07_bytes=r['bytes'],outcome='win' if r['makespan']<b['makespan'] else 'loss' if r['makespan']>b['makespan'] else 'tie'))
            for arm in ['fast','shared'] if i in PILOT else ['fast']:
                s=read(folder/arm/'search.json');invalid.extend(dict(case=i,cores=k,arm=arm,**x) for x in s['evaluations'] if x['status']!='ok')
                if i in PILOT:pilot.append(read(folder/arm/'row.json'))
            if i in PILOT:assert checks['shared_full_result_and_trajectory_exact']
    curves={'r05':read(BASE/'summary.json')['curves']['routed'],'r07':{'1':1.,**{str(k):statistics.mean(r['speedup'] for r in rows if r['cores']==k) for k in range(2,6)}}}
    totals={key:sum(r[key] for r in rows) for key in ['makespan','bytes','official_calls','cache_hits','solve_seconds']}
    timing={arm:{key:sum(r[key] for r in pilot if r['arm']==arm) for key in ['solve_seconds','candidate_seconds','official_calls','bytes','makespan']} for arm in ['fast','shared']}
    result=dict(status='full100_confirmed_shared_pilot_checked_not_promoted',curves=curves,outcomes={x:sum(p['outcome']==x for p in pairs) for x in ['win','tie','loss']},geomean_ratio=math.exp(statistics.mean(math.log(p['ratio']) for p in pairs)),worst=min(pairs,key=lambda p:p['ratio']),r07_totals=totals,paired14_timing=timing,
        checks=dict(fresh_B_final_replays=456,r07_configurations=400,shared_menus_exact=400,shared_full_trajectory_exact=56,global_capacity_pass=400,invalid_candidates=invalid),default_changed=False)
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h,n
    verify();write_json(OUT/'summary.json',result)
    for name,data in [('rows',rows),('pairs',pairs),('paired14',pilot)]:
        with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','launch','case','report']);p.add_argument('--workers',type=int,default=8);p.add_argument('--case',type=int);a=p.parse_args();{'freeze':freeze,'launch':lambda:launch(a.workers),'case':lambda:run_case(a.case),'report':report}[a.action]()
