"""Post-conformance structural routing pilot: no score-based case selection."""
import argparse,csv,gzip,json,math,statistics,time
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load
from q2_single_reference import fixed_reference_fast
from q2_structural_route import solve
from q2_resources import snapshot

OUT=ROOT/'图表/runs/20260924-A-q2-route-r04'
PHASES={'development':[12,48,50],'confirmation':[22,24,35]}
ARMS=['legacy','reference','routed']
Q1=ROOT/'图表/runs/20260924-A-q1-delivery-r02/solutions'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def freeze():
    assert not OUT.exists();settings,delay,prov=load()
    audit=ROOT/'审查/证据/20260924-A-q2-compliance-r04-v2/audit.json';assert read(audit)['research_optimization_eligible']
    c=dict(phases=PHASES,cores=[2,3,4,5],arms=ARMS,budget=12,seed=0,
           rule='largest weak compute component >50%: replace only base slots7-8 by reference HEFT counterparts; otherwise all legacy; slots1-6 protected; ordinary J slots9-12',
           sample_selection='Pre-score structural screen: 024 single component, 035 dominant component, 022 dispersed; unused in r02/r03 tuning, Q1 history known',
           gate='confirmation GM(routed/legacy speedup)>=1.005; >=2 improved graphs; no per-core mean regression; all final replays and slot protections pass',
           settings=settings,delay=delay,provenance=prov,resources=snapshot(),audit_sha256=sha(audit.read_bytes()),inputs={},plans={},
           sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')})
    for i in sum(PHASES.values(),[]):
        c['inputs'][str(i)]=sha((PROCESSED/f'data/case_{i:03}.json').read_bytes())
        for k in c['cores']:
            p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';c['plans'][p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    OUT.mkdir(parents=True);write_json(OUT/'contract.json',c)


def run(phase,i):
    c=read(OUT/'contract.json');assert i in PHASES[phase]
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    settings,delay,prov=load();p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)];raw=read(p)
    t=time.perf_counter();reference=fixed_reference_fast(raw,settings);ref_seconds=time.perf_counter()-t
    for k in c['cores']:
        p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';assert sha(p.read_bytes())==c['plans'][p.relative_to(ROOT).as_posix()];migration=read(p)
        arms=ARMS[(i+k)%3:]+ARMS[:(i+k)%3]
        for arm in arms:
            dest=OUT/phase/f'case_{i:03}/{k}/{arm}';assert not dest.exists()
            plan,result,stats=solve(raw,settings,delay,prov,k,migration,arm)
            row=dict(case=i,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],reference=reference['makespan'],reference_seconds=ref_seconds,
                     speedup=reference['makespan']/result['makespan'],**{name:stats[name] for name in ['base_makespan','slots','official_calls','cache_hits','solve_seconds','replay_seconds','replay_equal']})
            dest.mkdir(parents=True);write_json(dest/f'case_{i:03}_multicore_res.json',plan);write_json(dest/'search.json',stats);write_json(dest/'row.json',row)
            with gzip.open(dest/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
            print(phase,i,k,arm,row['makespan'],round(row['solve_seconds'],3),flush=True)


def report():
    c=read(OUT/'contract.json');summary={};allrows=[]
    lines=['# 问题二合规核查后结构准入实验 r04','','核心规则核查通过，正式全量交付未完成。保持同一B模型和普通J，仅比较初始放置策略。所有组12机会；routed保留legacy前6机会，仅在最大计算弱连通分量占比超过50%时替换第7/8机会。此阈值为多数分量定义，运行前固定，不按case编号或观察成绩选路。',
           '开发012/048/050；确认022（多分量）、024（单分量）、035（主导分量），按静态结构选定，未用于r02/r03调参；Q1历史已知。未叠加L、重划分或引导J。','']
    for phase,ids in PHASES.items():
        rows=[read(p) for p in sorted((OUT/phase).glob('case_*/*/*/row.json'))];assert len(rows)==36;allrows+=rows;index={(r['case'],r['cores'],r['arm']):r for r in rows}
        for i in ids:
            for k in range(2,6):
                s={a:read(OUT/phase/f'case_{i:03}/{k}/{a}/search.json') for a in ARMS}
                assert all(x['slots']==12 for x in s.values())
                assert [x['plan_sha256'] for x in s['legacy']['evaluations'][:6]]==[x['plan_sha256'] for x in s['routed']['evaluations'][:6]]
        curves={a:{'1':1.,**{str(k):statistics.mean(r['speedup'] for r in rows if r['arm']==a and r['cores']==k) for k in range(2,6)}} for a in ARMS};comparisons=[]
        for a in ['reference','routed']:
            pairs=[]
            for i in ids:
                for k in range(2,6):
                    old,new=index[i,k,'legacy'],index[i,k,a]
                    pairs.append(dict(case=i,cores=k,legacy=old['makespan'],challenger=new['makespan'],ratio=old['makespan']/new['makespan'],legacy_bytes=old['bytes'],challenger_bytes=new['bytes'],legacy_seconds=old['solve_seconds'],challenger_seconds=new['solve_seconds'],outcome='win' if new['makespan']<old['makespan'] else 'loss' if new['makespan']>old['makespan'] else 'tie'))
            gm=math.exp(statistics.mean(math.log(x['ratio']) for x in pairs));improved=sum(math.prod(x['ratio'] for x in pairs if x['case']==i)>1 for i in ids)
            gate=gm>=1.005 and improved>=2 and all(curves[a][str(k)]>=curves['legacy'][str(k)] for k in range(1,6))
            comparisons.append(dict(challenger=a,geomean_ratio=gm,outcomes={s:sum(x['outcome']==s for x in pairs) for s in ['win','tie','loss']},gate=gate,pairs=pairs))
            with (OUT/phase/f'{a}_paired.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
        summary[phase]=dict(curves=curves,comparisons=comparisons)
        lines += [f'## {phase}','','| 方法 | 1核 | 2核 | 3核 | 4核 | 5核 |','|---|---:|---:|---:|---:|---:|']
        for a in ARMS:lines.append('| '+a+' | '+' | '.join(f'{curves[a][str(k)]:.6f}' for k in range(1,6))+' |')
        lines += ['','| 方法 | 额外搬运合计bytes | 搜索合计s |','|---|---:|---:|']
        for a in ARMS:lines.append(f"| {a} | {sum(r['bytes'] for r in rows if r['arm']==a)} | {sum(r['solve_seconds'] for r in rows if r['arm']==a):.3f} |")
        lines.append('')
        for x in comparisons:
            lines.append(f"{x['challenger']}相对legacy：{x['outcomes']}；几何平均提速比变化{(x['geomean_ratio']-1)*100:+.6f}%；预设条件{x['gate']}。")
            for p in x['pairs']:
                if p['outcome']=='loss':lines.append(f"退步：case{p['case']:03}/{p['cores']}核，{p['legacy']}→{p['challenger']} cycles。")
        lines.append('')
    assert all(r['replay_equal'] for r in allrows)
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    for p,h in c['plans'].items():assert sha((ROOT/p).read_bytes())==h
    verify();summary['audit']=dict(final_replays=72,slots=sum(x['slots'] for x in allrows),actual_search_calls=sum(x['official_calls'] for x in allrows),cache_hits=sum(x['cache_hits'] for x in allrows),full100=False)
    lines += ['## 判断与边界','',f"路由策略确认条件：{summary['confirmation']['comparisons'][1]['gate']}。未更改默认、未完成全量交付。",'保护6个基础机会不保证完整legacy最优解不退步，被替换的第7/8机会或后续普通J轨迹仍可能带来机会损失；必须展示退步案例。不能把逐例最好值拼成统一算法。搜索seconds、执行cycles和搬运bytes分别报告；单次并行计时不是显著耗时结论。',json.dumps(summary['audit'])]
    write_json(OUT/'summary.json',summary)
    with (OUT/'all_rows.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
    report=ROOT/'审查/问题二结构准入对照_r04.md';assert not report.exists();report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({p:[{k:v for k,v in x.items() if k!='pairs'} for x in summary[p]['comparisons']] for p in PHASES}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','run','report']);p.add_argument('--phase',choices=list(PHASES));p.add_argument('--case',type=int);a=p.parse_args();{'freeze':freeze,'run':lambda:run(a.phase,a.case),'report':report}[a.action]()
