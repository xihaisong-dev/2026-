"""Locked diagnostic regression pilot, explicitly not independent confirmation."""
import argparse,concurrent.futures,csv,gzip,json,math,os,statistics,sys,time
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_full_campaign import OUT as OLD,Q1,read
from q2_evaluator import load
from q2_structural_route import solve as baseline
from q2_reserve_gate import solve as reserve
from q2_resources import snapshot

OUT=ROOT/'图表/runs/20260924-A-q2-reserve-r06'
CASES=[1,5,12,22,24,35,48,49,50,64,69,71,86,88]


def freeze():
    assert not OUT.exists();OUT.mkdir(parents=True)
    settings,delay,prov=load();old=read(OLD/'contract.json')
    sources={**old['sources'],**{n:sha((ROOT/'程序'/n).read_bytes()) for n in ['q2_reserve_gate.py','q2_reserve_campaign.py']}}
    write_json(OUT/'contract.json',dict(status='posthoc_diagnostic_pilot_not_holdout',cases=CASES,cores=[2,3,4,5],arms=['routed','reserve'],
        budget=12,seed=0,settings=settings,delay=delay,provenance=prov,sources=sources,
        fixed_rule='Keep every distinct routed base candidate and its tie priority; use duplicate menu slots for missing old slots7/8, in that order; ordinary J4 unchanged.',
        evaluation_accounting='Same 12 opportunities, NOT necessarily equal actual official calls. Extra calls and timing must be reported.',
        decision='No default adoption from this posthoc selected sample. Progress only if no per-core mean speedup regression; report all losses, bytes and solver time.',
        diagnosis_sha256=sha((ROOT/'图表/runs/20260924-A-q2-diagnosis-r06/summary.json').read_bytes()),
        inputs={str(i):old['inputs'][str(i)] for i in CASES},old_contract_sha256=sha((OLD/'contract.json').read_bytes()),
        plans={p:h for p,h in old['plans'].items() if any(f'case_{i:03}_' in p for i in CASES)}))


def one(i):
    c=read(OUT/'contract.json')
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h,n
    settings,delay,prov=load();assert (settings,delay,prov)==(c['settings'],c['delay'],c['provenance'])
    p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)];raw=read(p)
    folder=OUT/f'cases/case_{i:03}';assert not folder.exists();folder.mkdir(parents=True)
    for k in c['cores']:
        p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';assert sha(p.read_bytes())==c['plans'][p.relative_to(ROOT).as_posix()];migration=read(p)
        for arm in (['routed','reserve'] if (i+k)%2 else ['reserve','routed']):
            plan,result,stats=baseline(raw,settings,delay,prov,k,migration,'routed') if arm=='routed' else reserve(raw,settings,delay,prov,k,migration)
            old=OLD/f'cases/case_{i:03}/{k}/routed';oldrow=read(old/'row.json')
            if arm=='routed':
                assert plan==read(old/f'case_{i:03}_multicore_res.json')
                with gzip.open(old/'evaluation.json.gz','rt',encoding='utf-8') as f:assert result==json.load(f)
            row=dict(case=i,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],reference=oldrow['reference'],
                     speedup=oldrow['reference']/result['makespan'],**{n:stats[n] for n in ['slots','official_calls','cache_hits','solve_seconds','replay_seconds','replay_equal']},admitted_old_candidates=stats.get('admitted_old_candidates',0))
            dest=folder/f'{k}/{arm}';dest.mkdir(parents=True);write_json(dest/f'case_{i:03}_multicore_res.json',plan);write_json(dest/'search.json',stats);write_json(dest/'row.json',row)
            with gzip.open(dest/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
    write_json(folder/'complete.json',dict(case=i,complete=True));return i


def launch(workers):
    c=read(OUT/'contract.json');r=snapshot(worker_gib=1.);assert workers<=r['recommended_workers']
    assert not (OUT/'execution.json').exists();write_json(OUT/'execution.json',dict(resources=r,workers=workers))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i in pool.map(one,sorted(c['cases'],key=lambda i:-(PROCESSED/f'data/case_{i:03}.json').stat().st_size)):
            print('FINISHED',i,flush=True)


def report():
    c=read(OUT/'contract.json');rows=[];pairs=[]
    for i in c['cases']:
        assert read(OUT/f'cases/case_{i:03}/complete.json')['complete']
        for k in c['cores']:
            rr={}
            for arm in c['arms']:
                folder=OUT/f'cases/case_{i:03}/{k}/{arm}';r=read(folder/'row.json');assert r['slots']==12 and r['replay_equal'];rows.append(r);rr[arm]=r
            a,b=rr['routed'],rr['reserve'];oldlegacy=read(OLD/f'cases/case_{i:03}/{k}/legacy/row.json')
            pairs.append(dict(case=i,cores=k,routed=a['makespan'],reserve=b['makespan'],ratio=a['makespan']/b['makespan'],old_legacy=oldlegacy['makespan'],
                outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie',routed_bytes=a['bytes'],reserve_bytes=b['bytes']))
    curves={a:{'1':1.,**{str(k):statistics.mean(r['speedup'] for r in rows if r['arm']==a and r['cores']==k) for k in c['cores']}} for a in c['arms']}
    totals={a:{key:sum(r[key] for r in rows if r['arm']==a) for key in ['bytes','official_calls','cache_hits','solve_seconds','replay_seconds']} for a in c['arms']}
    s=dict(status='posthoc_pilot_complete_not_independent_confirmation',curves=curves,totals=totals,
        geomean_ratio=math.exp(statistics.mean(math.log(p['ratio']) for p in pairs)),outcomes={x:sum(p['outcome']==x for p in pairs) for x in ['win','tie','loss']},
        per_core_gate=all(curves['reserve'][str(k)]>=curves['routed'][str(k)] for k in c['cores']),
        original_16_losses_recovered=sum(p['reserve']<=p['old_legacy'] for p in pairs if p['routed']>p['old_legacy']),
        actual_replays=len(rows),search_slots=12*len(rows),default_changed=False)
    for n,h in c['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h
    write_json(OUT/'summary.json',s)
    for name,rr in [('rows.csv',rows),('paired.csv',pairs)]:
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    print(json.dumps(s,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','launch','report']);p.add_argument('--workers',type=int,default=4);a=p.parse_args();{'freeze':freeze,'launch':lambda:launch(a.workers),'report':report}[a.action]()
