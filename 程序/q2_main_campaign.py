"""Versioned pilot of Q2 on current main; phases selected before outcomes."""
import argparse,csv,gzip,json,math,statistics,time,subprocess
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load,fixed_reference
from q2_current import solve
from q2_resources import snapshot

OUT=ROOT/'图表/runs/20260924-A-q2-main-r02'
Q1=ROOT/'图表/runs/20260924-A-q1-delivery-r02/solutions'
PHASES={'development':[6,48,50],'validation':[12,39,72],'scale':[14,91]}


def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);write_json(p,v)


def freeze():
    if OUT.exists():raise FileExistsError(OUT)
    settings,delay,prov=load()
    cases=sum(PHASES.values(),[])
    contract=dict(main_commit='50b91d46a7bd43ca404c1285dfc27929496bf266',phases=PHASES,cores=[2,3,4,5],scale_cores=[2,5],seed=0,
        variants=['ordinary','guided'],budget=12,base_slots=8,repair_slots=4,settings=settings,delay=delay,provenance=prov,
        gate='validation guided/ordinary geometric time advantage >=0.5%; >=2 improved graphs; no mean speedup regression at any core; all scales valid; no baseline displacement.',
        sample_note='Known Q1 structures and legacy Q2 history; held out from current-rule tuning, not external blind validation.',
        resources=snapshot(),inputs={},q1_protected_hashes={},sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')})
    for i in cases:
        contract['inputs'][str(i)]=sha((PROCESSED/f'data/case_{i:03}.json').read_bytes())
        for k in range(2,6):
            p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';contract['q1_protected_hashes'][p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    dump(OUT/'contract.json',contract)


def run(phase,case=None):
    c=json.loads((OUT/'contract.json').read_text(encoding='utf-8'))
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    settings,delay,_=load()
    for i in ([case] if case else c['phases'][phase]):
        assert i in c['phases'][phase]
        p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)]
        raw=json.loads(p.read_text(encoding='utf-8'));t=time.perf_counter();reference=fixed_reference(raw,settings);ref_seconds=time.perf_counter()-t
        for k in (c['scale_cores'] if phase=='scale' else c['cores']):
            migration=Q1/f'{k}cores/case_{i:03}_multicore_res.json'
            assert sha(migration.read_bytes())==c['q1_protected_hashes'][migration.relative_to(ROOT).as_posix()]
            plan=json.loads(migration.read_text(encoding='utf-8'))
            variants=c['variants'] if (i+k)%2 else list(reversed(c['variants']))
            for mode in variants:
                dest=OUT/phase/f'case_{i:03}/{k}/{mode}'
                if dest.exists():raise FileExistsError(dest)
                start=time.perf_counter();best,result,stats=solve(raw,settings,delay,c['provenance'],k,plan,mode)
                row=dict(case=i,cores=k,mode=mode,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],
                         reference=reference['makespan'],speedup=reference['makespan']/result['makespan'],reference_seconds=ref_seconds,
                         solve_seconds=stats['solve_seconds'],replay_seconds=stats['replay_seconds'],total_seconds=time.perf_counter()-start,
                         base_makespan=stats['base_makespan'],migration_makespan=stats['evaluations'][0].get('makespan'),
                         slots=stats['slots'],official_calls=stats['official_calls'],hits=stats['cache_hits'],replay_equal=stats['final_replay_equal'])
                dump(dest/f'case_{i:03}_multicore_res.json',best);dump(dest/'search.json',stats);dump(dest/'row.json',row)
                with gzip.open(dest/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
                print(phase,i,k,mode,result['makespan'],'seconds',round(row['solve_seconds'],3),flush=True)
    summarize(phase)


def summarize(phase):
    rows=[]
    for p in sorted((OUT/phase).glob('case_*/*/ordinary/row.json')):
        other=p.parent.parent/'guided/row.json'
        if not other.exists():continue
        a=json.loads(p.read_text());b=json.loads(other.read_text())
        sa=json.loads((p.parent/'search.json').read_text());sb=json.loads((other.parent/'search.json').read_text())
        assert [x['plan_sha256'] for x in sa['evaluations'][:8]]==[x['plan_sha256'] for x in sb['evaluations'][:8]]
        assert a['base_makespan']==b['base_makespan'] and a['slots']==b['slots']==12
        rows.append(dict(case=a['case'],cores=a['cores'],migration=a['migration_makespan'],base=a['base_makespan'],ordinary=a['makespan'],guided=b['makespan'],
                         ordinary_bytes=a['bytes'],guided_bytes=b['bytes'],ordinary_speedup=a['speedup'],guided_speedup=b['speedup'],
                         ratio=a['makespan']/b['makespan'],ordinary_seconds=a['solve_seconds'],guided_seconds=b['solve_seconds'],
                         outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie'))
    if not rows:return
    curves={v:{'1':1.,**{str(k):statistics.mean(x[v+'_speedup'] for x in rows if x['cores']==k) for k in sorted({x['cores'] for x in rows})}} for v in ['ordinary','guided']}
    gm=math.exp(statistics.mean(math.log(x['ratio']) for x in rows))
    gains={str(i):math.exp(statistics.mean(math.log(x['ratio']) for x in rows if x['case']==i)) for i in {x['case'] for x in rows}}
    summary=dict(phase=phase,rows=rows,curves=curves,geomean_ratio=gm,per_graph_ratio=gains,
                 outcomes={s:sum(x['outcome']==s for x in rows) for s in ['win','tie','loss']},
                 gate=gm>=1.005 and sum(x>1 for x in gains.values())>=2 and all(curves['guided'][k]>=curves['ordinary'][k] for k in curves['ordinary']))
    dump(OUT/phase/'summary.json',summary)
    with (OUT/phase/'paired.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze']+list(PHASES));p.add_argument('--case',type=int);a=p.parse_args()
    freeze() if a.phase=='freeze' else run(a.phase,a.case)
