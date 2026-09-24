"""Frozen engineering regression and separately labelled new synthetic validation."""
import argparse,concurrent.futures,csv,gzip,json,math,random,statistics,time
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,official
from q2_evaluator import load,key,fixed_reference
from q2_resources import snapshot
from q2_reserve_gate import solve as reserve
from q2_reserve_fast import solve as fast
from q2_structural_route import solve as routed
from q2_full_campaign import Q1,read
from q2_physical import PhysicalScorer

OUT=ROOT/'图表/runs/20260924-A-q2-overhead-r07'
DATA=ROOT/'数据/processed/q2-synthetic-r07'
OLD=ROOT/'图表/runs/20260924-A-q2-reserve-r06-v2'
CASES=[1,5,12,22,24,35,48,49,50,64,69,71,86,88]
SPECS=[dict(name=f'{family}_{n}',family=family,n=n,seed=2026092400+j*10+k)
       for j,family in enumerate(['components','forkjoin','layered','pressure']) for k,n in enumerate([128,512])]
SPECS += [dict(name=f'{f}_2048',family=f,n=2048,seed=2026092490+j) for j,f in enumerate(['layered','pressure'])]

def generate(spec):
    rng=random.Random(spec['seed']);n=spec['n'];family=spec['family'];links=set()
    if family=='components':
        for u in range(n):
            if u%16:links.add((u-1,u))
    else:
        width=8 if family=='forkjoin' else 16 if family=='layered' else 32
        for u in range(width,n):
            start=((u//width)-1)*width
            parents={start+u%width,start+(u+1)%width} if family=='forkjoin' else set(rng.sample(range(start,start+width),2))
            links.update((p,u) for p in parents)
    ops=[dict(id=u,op='CUSTOM',pipe=('PIPE_V' if family=='pressure' else rng.choice(['PIPE_M','PIPE_V'])),cycles=rng.randint(500,5000)) for u in range(n)]
    tensors=[dict(id=n+u,pos=('UB' if family=='pressure' else rng.choice(['UB','L1'])),size=(32768 if family=='pressure' else rng.choice([60,960,7680,15360]))) for u in range(n)]
    edges=[dict(source=u,target=n+u) for u in range(n)]+[dict(source=n+u,target=v) for u,v in sorted(links)]
    return dict(ops=ops,tensors=tensors,edges=edges)

def freeze():
    assert not (OUT/'contract.json').exists() and not DATA.exists();DATA.mkdir(parents=True)
    settings,delay,prov=load()
    from evaluation_validation import validate_graph
    inputs={}
    for spec in SPECS:
        raw=generate(spec);validate_graph(raw);p=DATA/(spec['name']+'.json');write_json(p,raw);inputs[spec['name']]=sha(p.read_bytes())
    c=dict(status='engineering_regression_plus_synthetic_only',cases=CASES,specs=SPECS,inputs=inputs,cores=[2,3,4,5],budget=12,seed=0,
           settings=settings,delay=delay,provenance=prov,sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')},
           previous_contract_sha256=sha((OLD/'contract.json').read_bytes()),
           scope='All official100 previously inspected. New synthetic cases are NOT official unseen confirmation. Freeze before any outcome; no tuning on these results.',
           equivalence='Same complete serialized plan and official result; same base anchor and four J proposals. Remaining duplicate slots may move; first distinct candidate order must agree.',
           timing='Same host, same worker pool, arm order rotated. Search excludes common Q1 seed, prescribed single reference, final replay and audit. No comparison of timings across earlier campaigns.')
    write_json(DATA/'manifest.json',dict(synthetic=True,official=False,specs=SPECS,inputs=inputs,generator_sha256=c['sources']['q2_overhead_campaign.py']))
    write_json(OUT/'contract.json',c)
    print('FROZEN',len(inputs))

def normalized(x):return json.loads(json.dumps(x))

def one(job):
    kind,name=job;c=read(OUT/'contract.json')
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h,n
    settings,delay,prov=load();assert (settings,delay,prov)==(c['settings'],c['delay'],c['provenance'])
    dest=OUT/kind/str(name);assert not dest.exists();dest.mkdir(parents=True)
    if kind=='regression':
        prior=read(OLD/'contract.json');p=PROCESSED/f'data/case_{name:03}.json';assert sha(p.read_bytes())==prior['inputs'][str(name)]
        raw=read(p);ref=read(OLD/f'cases/case_{name:03}/2/reserve/row.json')['reference'];reference_seconds=0.
    else:
        p=DATA/f'{name}.json';assert sha(p.read_bytes())==c['inputs'][name];raw=read(p)
        from evaluation_validation import validate_graph
        validate_graph(raw);t=time.perf_counter();reference=fixed_reference(raw,settings);reference_seconds=time.perf_counter()-t;ref=reference['makespan']
        write_json(dest/'reference.json',dict(makespan=ref,seconds=reference_seconds,backend='official_singlecore',added_copy_bytes=reference['data_movement_bytes']['added_copy_bytes']))
    for k in c['cores']:
        if kind=='regression':
            p=Q1/f'{k}cores/case_{name:03}_multicore_res.json';assert sha(p.read_bytes())==prior['plans'][p.relative_to(ROOT).as_posix()];migration=read(p);seed_seconds=0
        else:
            from q1_experimental import solve_experimental
            from q1_submit import BASELINE_FEATURES
            waits=official().read_scene_a_config(str(PROCESSED/'data/config.txt'));t=time.perf_counter()
            migration,_,seed_stats=solve_experimental(raw,settings,waits,k,12,0,BASELINE_FEATURES,evaluator_backend='counter');seed_seconds=time.perf_counter()-t
            write_json(dest/f'seed_{k}.json',dict(plan=migration,stats=seed_stats,seconds=seed_seconds))
        arms=['reserve','fast'] if kind=='regression' else ['routed','reserve','fast']
        offset=(k+(int(name) if kind=='regression' else len(name)))%len(arms);arms=arms[offset:]+arms[:offset];answers={}
        for arm in arms:
            plan,result,stats=routed(raw,settings,delay,prov,k,migration,'routed') if arm=='routed' else (reserve if arm=='reserve' else fast)(raw,settings,delay,prov,k,migration)
            assert stats['slots']==12 and stats['replay_equal']
            row=dict(kind=kind,case=name,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],reference=ref,speedup=ref/result['makespan'],
                **{x:stats[x] for x in ['official_calls','cache_hits','solve_seconds','replay_seconds']},seed_seconds=seed_seconds,reference_seconds=reference_seconds,
                assessment_seconds=sum(x['seconds'] for x in stats['evaluations']),invalid_candidates=sum(x['status']!='ok' for x in stats['evaluations']))
            folder=dest/str(k)/arm;folder.mkdir(parents=True);write_json(folder/'plan.json',plan);write_json(folder/'row.json',row);write_json(folder/'search.json',stats)
            with gzip.open(folder/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
            answers[arm]=(plan,result,stats)
        a,b=answers['reserve'],answers['fast'];assert a[0]==b[0] and normalized(a[1])==normalized(b[1])
        assert a[2]['base_plan_sha256']==b[2]['base_plan_sha256']
        assert [(r['plan_sha256'],r['makespan'],r['bytes']) for r in a[2]['evaluations'][8:]]==[(r['plan_sha256'],r['makespan'],r['bytes']) for r in b[2]['evaluations'][8:]]
        if kind=='regression':
            old=OLD/f'cases/case_{name:03}/{k}/reserve';assert b[0]==read(old/f'case_{name:03}_multicore_res.json')
            with gzip.open(old/'evaluation.json.gz','rt',encoding='utf-8') as f:assert normalized(b[1])==json.load(f)
        t=time.perf_counter();profiles=PhysicalScorer(raw,settings,delay).actual_lifetimes(b[0],b[1])
        write_json(dest/str(k)/'checks.json',dict(complete_plan_and_result_equal=True,anchor_and_J_equal=True,global_capacity_pass=True,peaks={str(c):p['peak_bytes'] for c,p in profiles.items()},audit_seconds=time.perf_counter()-t))
    write_json(dest/'complete.json',dict(complete=True));return job

def launch(workers):
    r=snapshot();assert workers<=r['recommended_workers'];assert not (OUT/'execution.json').exists();write_json(OUT/'execution.json',dict(resources=r,workers=workers))
    jobs=[('regression',i) for i in CASES]+[('synthetic',s['name']) for s in SPECS]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(one,jobs):print('COMPLETE',job,flush=True)

def report():
    summaries={}
    for kind,names in [('regression',CASES),('synthetic',[s['name'] for s in SPECS])]:
        rows=[]
        for name in names:
            assert read(OUT/kind/str(name)/'complete.json')['complete']
            for p in (OUT/kind/str(name)).glob('*/*/row.json'):rows.append(read(p))
        arms=sorted({r['arm'] for r in rows});totals={a:{k:sum(r[k] for r in rows if r['arm']==a) for k in ['makespan','bytes','official_calls','cache_hits','solve_seconds','assessment_seconds','invalid_candidates']} for a in arms}
        curves={a:{'1':1.,**{str(k):statistics.mean(r['speedup'] for r in rows if r['arm']==a and r['cores']==k) for k in range(2,6)}} for a in arms}
        pairs=[];base='reserve' if kind=='regression' else 'routed'
        for name in names:
            for k in range(2,6):
                d={r['arm']:r for r in rows if r['case']==name and r['cores']==k};a,b=d[base],d['fast'];pairs.append(dict(case=name,cores=k,base=base,base_cycles=a['makespan'],fast_cycles=b['makespan'],ratio=a['makespan']/b['makespan'],outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie',base_bytes=a['bytes'],fast_bytes=b['bytes']))
        summaries[kind]=dict(totals=totals,curves=curves,outcomes={x:sum(p['outcome']==x for p in pairs) for x in ['win','tie','loss']},geomean_ratio=math.exp(statistics.mean(math.log(p['ratio']) for p in pairs)),worst=min(pairs,key=lambda p:p['ratio']),comparisons=len(pairs),equivalence_and_capacity_checks=len(pairs))
        for label,data in [('rows',rows),('pairs',pairs)]:
            with (OUT/f'{kind}_{label}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write_json(OUT/'summary.json',dict(status='completed_not_promoted',**summaries,official_unseen_confirmation=False));print(json.dumps(summaries,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','launch','report']);p.add_argument('--workers',type=int,default=4);a=p.parse_args();{'freeze':freeze,'launch':lambda:launch(a.workers),'report':report}[a.action]()
