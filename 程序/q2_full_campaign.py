"""Full100 locked legacy/routed comparison after the independent routing pilot."""
import argparse,concurrent.futures,csv,gzip,json,os,subprocess,sys,time,math,statistics
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load
from q2_single_reference import fixed_reference_fast
from q2_structural_route import solve
from q2_resources import snapshot

OUT=ROOT/'图表/runs/20260924-A-q2-full-r05'
Q1=ROOT/'图表/runs/20260924-A-q1-delivery-r02/solutions'
ARMS=['legacy','routed']


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def freeze():
    assert not OUT.exists();pilot=ROOT/'图表/runs/20260924-A-q2-route-r04/summary.json'
    assert read(pilot)['confirmation']['comparisons'][1]['gate']
    settings,delay,prov=load();c=dict(cases=list(range(1,101)),cores=[2,3,4,5],arms=ARMS,budget=12,seed=0,
        selection='One global algorithm, no casewise best-of. Keep legacy if routed GM<1.005 or any per-core mean speedup regresses; bytes separately reported.',
        pilot_sha256=sha(pilot.read_bytes()),settings=settings,delay=delay,provenance=prov,
        sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')},inputs={},plans={},fixed_references={})
    with (ROOT/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig') as f:
        c['fixed_references']={x['case']:int(x['single_makespan']) for x in csv.DictReader(f)}
    for i in c['cases']:
        p=PROCESSED/f'data/case_{i:03}.json';c['inputs'][str(i)]=sha(p.read_bytes())
        for k in c['cores']:
            p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';c['plans'][p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    OUT.mkdir(parents=True);write_json(OUT/'contract.json',c)


def run_case(i):
    c=read(OUT/'contract.json');assert i in c['cases']
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    settings,delay,prov=load();assert prov==c['provenance'];p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)];raw=read(p)
    folder=OUT/f'cases/case_{i:03}';assert not folder.exists();folder.mkdir(parents=True)
    t=time.perf_counter();reference=fixed_reference_fast(raw,settings);reference_seconds=time.perf_counter()-t
    assert reference['makespan']==c['fixed_references'][f'case_{i:03}']
    with gzip.open(folder/'fixed_single.json.gz','wt',encoding='utf-8') as f:json.dump(reference,f)
    write_json(folder/'fixed_single_metadata.json',dict(makespan=reference['makespan'],seconds=reference_seconds,backend='pinned_exact_counter',same_prescribed_reference=True))
    for k in c['cores']:
        p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';assert sha(p.read_bytes())==c['plans'][p.relative_to(ROOT).as_posix()];migration=read(p)
        for arm in (ARMS if (i+k)%2 else ARMS[::-1]):
            dest=folder/f'{k}/{arm}';assert not dest.exists()
            plan,result,stats=solve(raw,settings,delay,prov,k,migration,arm)
            row=dict(case=i,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],reference=reference['makespan'],speedup=reference['makespan']/result['makespan'],
                **{x:stats[x] for x in ['slots','official_calls','cache_hits','solve_seconds','replay_seconds','replay_equal','base_makespan']})
            dest.mkdir(parents=True);write_json(dest/f'case_{i:03}_multicore_res.json',plan);write_json(dest/'row.json',row);write_json(dest/'search.json',stats)
            with gzip.open(dest/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
            print(i,k,arm,row['makespan'],round(row['solve_seconds'],3),flush=True)
    write_json(folder/'complete.json',dict(case=i,rows=8,complete=True))


def launch(workers):
    resources=snapshot(worker_gib=4.)
    assert workers<=resources['recommended_workers'],resources
    dest=OUT/'execution.json';assert not dest.exists();write_json(dest,dict(resources=resources,workers=workers,commands='python q2_full_campaign.py case --case N',concurrency='independent case processes, alternate arm order within each case'))
    logdir=OUT/'logs';logdir.mkdir()
    # Long cases first, assigned dynamically; never change search or candidate budgets.
    ids=sorted(range(1,101),key=lambda i:-(PROCESSED/f'data/case_{i:03}.json').stat().st_size)
    def one(i):
        with (logdir/f'case_{i:03}.txt').open('w',encoding='utf-8') as f:
            p=subprocess.run([sys.executable,__file__,'case','--case',str(i)],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
        return i,p.returncode
    done=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        jobs=[executor.submit(one,i) for i in ids]
        for future in concurrent.futures.as_completed(jobs):
            i,code=future.result();done.append(dict(case=i,returncode=code));write_json(OUT/'progress.json',dict(completed=len(done),failed=[x for x in done if x['returncode']],jobs=done));print('FINISHED',i,code,'TOTAL',len(done),flush=True)
    assert not [x for x in done if x['returncode']],done


def report():
    c=read(OUT/'contract.json');rows=[];pairs=[];invalid=[];concordance=0
    for i in c['cases']:
        assert read(OUT/f'cases/case_{i:03}/complete.json')['complete']
        for k in c['cores']:
            data={};search={}
            for arm in ARMS:
                folder=OUT/f'cases/case_{i:03}/{k}/{arm}';r=read(folder/'row.json');s=read(folder/'search.json')
                assert r['slots']==12 and r['replay_equal'];rows.append(r);data[arm]=r;search[arm]=s
                invalid.extend(dict(case=i,cores=k,arm=arm,**x) for x in s['evaluations'] if x['status']!='ok')
                phase='development' if i in [12,48,50] else 'confirmation'
                old=ROOT/f'图表/runs/20260924-A-q2-route-r04/{phase}/case_{i:03}/{k}/{arm}'
                if old.exists():
                    assert read(old/'row.json')['makespan']==r['makespan'];assert read(old/f'case_{i:03}_multicore_res.json')==read(folder/f'case_{i:03}_multicore_res.json');concordance+=1
            assert [x['plan_sha256'] for x in search['legacy']['evaluations'][:6]]==[x['plan_sha256'] for x in search['routed']['evaluations'][:6]]
            a,b=data['legacy'],data['routed'];pairs.append(dict(case=i,cores=k,legacy=a['makespan'],routed=b['makespan'],ratio=a['makespan']/b['makespan'],legacy_bytes=a['bytes'],routed_bytes=b['bytes'],outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie'))
    assert len(rows)==800 and len(pairs)==400
    curves={a:{'1':1.,**{str(k):statistics.mean(x['speedup'] for x in rows if x['arm']==a and x['cores']==k) for k in c['cores']}} for a in ARMS}
    gm=math.exp(statistics.mean(math.log(x['ratio']) for x in pairs));gate=gm>=1.005 and all(curves['routed'][str(k)]>=curves['legacy'][str(k)] for k in c['cores'])
    adopted='routed' if gate else 'legacy'
    summary=dict(status='full100_evaluated',curves=curves,geomean_ratio=gm,outcomes={s:sum(x['outcome']==s for x in pairs) for s in ['win','tie','loss']},gate=gate,selected_global_algorithm=adopted,
        audit=dict(final_replays=800,search_slots=sum(x['slots'] for x in rows),actual_search_calls=sum(x['official_calls'] for x in rows),cache_hits=sum(x['cache_hits'] for x in rows),pilot_concordance=concordance,invalid_candidates=invalid),
        totals={a:dict(bytes=sum(x['bytes'] for x in rows if x['arm']==a),solve_seconds=sum(x['solve_seconds'] for x in rows if x['arm']==a)) for a in ARMS})
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    for p,h in c['plans'].items():assert sha((ROOT/p).read_bytes())==h
    verify();write_json(OUT/'summary.json',summary)
    for name,rs in [('all_rows.csv',rows),('paired.csv',pairs)]:
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','case','launch','report']);p.add_argument('--case',type=int);p.add_argument('--workers',type=int,default=10);a=p.parse_args();{'freeze':freeze,'case':lambda:run_case(a.case),'launch':lambda:launch(a.workers),'report':report}[a.action]()
