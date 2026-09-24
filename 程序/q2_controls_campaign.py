"""Frozen placement-only and fixed-base 4/0, 2/2, 0/4 J ablations."""
import argparse,csv,gzip,json,time,statistics,math
from pathlib import Path
from q1_io import ROOT,PROCESSED,sha,write_json,verify
from q2_evaluator import load
from q2_single_reference import fixed_reference_fast
from q2_controlled import solve,candidates,heft
from q2_resources import snapshot

OUT=ROOT/'图表/runs/20260924-A-q2-controls-r03'
PHASES={'development':[12,48,50],'confirmation':[18,33,67]}
ARMS=['placement_reference','placement_corrected','j_ordinary','j_mixed','j_guided']
Q1=ROOT/'图表/runs/20260924-A-q1-delivery-r02/solutions'


def freeze():
    assert not OUT.exists();verify();settings,delay,prov=load()
    c=dict(phases=PHASES,arms=ARMS,cores=[2,3,4,5],seed=0,placement_slots=8,j_slots=12,
        control='same partitions/rank/duration/menu; corrected cross-transfer accounting only; J always reference HEFT base; fixed 2+2 slots, no refill',
        scope='Inherited Q2 model; no L or repartition repair; confirmation unused in r02 tuning, Q1 history known, not blind external test',
        gate='Each challenge: confirmation GM >=1.005, >=2 improved graphs, no per-core mean speedup regression, all replay/legality checks pass; otherwise no promotion or full100',
        settings=settings,delay=delay,provenance=prov,local_resources=snapshot(),inputs={},plans={},
        sources={p.name:sha(p.read_bytes()) for p in (ROOT/'程序').glob('*.py')})
    for i in sum(PHASES.values(),[]):
        c['inputs'][str(i)]=sha((PROCESSED/f'data/case_{i:03}.json').read_bytes())
        for k in range(2,6):
            p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';c['plans'][p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    OUT.mkdir(parents=True);write_json(OUT/'contract.json',c)


def run(phase,i):
    c=json.loads((OUT/'contract.json').read_text(encoding='utf-8'));assert i in c['phases'][phase]
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    settings,delay,prov=load();p=PROCESSED/f'data/case_{i:03}.json';assert sha(p.read_bytes())==c['inputs'][str(i)]
    raw=json.loads(p.read_text(encoding='utf-8'));t=time.perf_counter();reference=fixed_reference_fast(raw,settings);reference_seconds=time.perf_counter()-t
    for k in c['cores']:
        p=Q1/f'{k}cores/case_{i:03}_multicore_res.json';assert sha(p.read_bytes())==c['plans'][p.relative_to(ROOT).as_posix()]
        migration=json.loads(p.read_text(encoding='utf-8'));arms=ARMS[(i+k)%5:]+ARMS[:(i+k)%5]
        for arm in arms:
            dest=OUT/phase/f'case_{i:03}/{k}/{arm}'
            if dest.exists():raise FileExistsError(dest)
            plan,result,stats=solve(raw,settings,delay,prov,k,migration,arm)
            row=dict(case=i,cores=k,arm=arm,makespan=result['makespan'],bytes=result['data_movement_bytes']['added_copy_bytes'],
                     reference=reference['makespan'],reference_seconds=reference_seconds,speedup=reference['makespan']/result['makespan'],
                     **{name:stats[name] for name in ['base_makespan','base_bytes','base_plan_sha256','slots','official_calls','cache_hits','solve_seconds','replay_seconds','diagnostic_seconds','replay_equal']})
            dest.mkdir(parents=True);write_json(dest/'plan.json',plan);write_json(dest/'search.json',stats);write_json(dest/'row.json',row)
            with gzip.open(dest/'evaluation.json.gz','wt',encoding='utf-8') as f:json.dump(result,f)
            print(phase,i,k,arm,row['makespan'],round(row['solve_seconds'],3),flush=True)


def report():
    c=json.loads((OUT/'contract.json').read_text(encoding='utf-8'));allrows=[];summary={}
    lines=['# 问题二初解通信对照与J预算分配 r03','','同一B模型、官方评估器及固定单核分母；未改Q1成绩。初解两组各8次机会，J三组各8基础+4修复机会；两类实验分别比较，不把8和12次预算作为同预算对照。',
      '初解固定划分、rank、持续时间代理、HEFT调度框架，仅改变内部跨核张量通信去重及直接边计费。外部输入和输出的局部成本保持参考估计，不声称本轮解决了所有通信估计误差。J固定参考HEFT基础，混合取普通前2和引导前2，重复仍占名额；不事后补位。',
      '开发012/048/050含既有退步样本；确认018/033/067在r02未用于调整，但Q1历史已知，非外部盲测。确定性seed0，先冻结协议，全部结果保留。','']
    for phase,cases in PHASES.items():
        rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((OUT/phase).glob('case_*/*/*/row.json'))]
        assert len(rows)==len(cases)*4*5,(phase,len(rows));allrows+=rows
        indexed={(r['case'],r['cores'],r['arm']):r for r in rows}
        for i in cases:
            for k in range(2,6):
                searches={a:json.loads((OUT/phase/f'case_{i:03}/{k}/{a}/search.json').read_text(encoding='utf-8')) for a in ARMS}
                ref=searches['placement_reference']['evaluations']
                assert len(ref)==8
                assert [x['partition_sha256'] for x in ref]==[x['partition_sha256'] for x in searches['placement_corrected']['evaluations']]
                for a in ARMS[2:]:
                    s=searches[a];assert len(s['evaluations'])==12
                    assert [x['plan_sha256'] for x in ref]==[x['plan_sha256'] for x in s['evaluations'][:8]]
                    assert s['base_plan_sha256']==searches['placement_reference']['base_plan_sha256']
                    assert indexed[i,k,a]['makespan']<=s['base_makespan']
                mixed=searches['j_mixed']['evaluations'][8:]
                assert [x['plan_sha256'] for x in mixed]==[x['plan_sha256'] for x in searches['j_ordinary']['evaluations'][8:10]+searches['j_guided']['evaluations'][8:10]]
        curves={a:{'1':1.,**{str(k):statistics.mean(r['speedup'] for r in rows if r['arm']==a and r['cores']==k) for k in range(2,6)}} for a in ARMS}
        comparisons=[]
        for baseline,challenger in [('placement_reference','placement_corrected'),('j_ordinary','j_mixed'),('j_ordinary','j_guided')]:
            paired=[]
            for i in cases:
                for k in range(2,6):
                    a,b=indexed[i,k,baseline],indexed[i,k,challenger]
                    paired.append(dict(case=i,cores=k,baseline=a['makespan'],challenger=b['makespan'],ratio=a['makespan']/b['makespan'],
                         baseline_bytes=a['bytes'],challenger_bytes=b['bytes'],baseline_seconds=a['solve_seconds'],challenger_seconds=b['solve_seconds'],
                         outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie'))
            gm=math.exp(statistics.mean(math.log(x['ratio']) for x in paired));gains=[math.prod(x['ratio'] for x in paired if x['case']==i)**.25 for i in cases]
            outcome={s:sum(x['outcome']==s for x in paired) for s in ['win','tie','loss']}
            gate=gm>=1.005 and sum(x>1 for x in gains)>=2 and all(curves[challenger][str(k)]>=curves[baseline][str(k)] for k in range(1,6))
            comparisons.append(dict(baseline=baseline,challenger=challenger,geomean_ratio=gm,outcomes=outcome,gate=gate,paired=paired))
            p=OUT/phase/f'{challenger}_paired.csv'
            with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
        summary[phase]=dict(curves=curves,comparisons=comparisons)
        lines += [f'## {phase}','','| 方法 | 1核 | 2核 | 3核 | 4核 | 5核 |','|---|---:|---:|---:|---:|---:|']
        for arm,curve in curves.items():lines.append('| '+arm+' | '+' | '.join(f'{curve[str(k)]:.6f}' for k in range(1,6))+' |')
        lines += ['','| 方法 | 额外搬运合计bytes | 搜索耗时合计s |','|---|---:|---:|']
        for arm in ARMS:
            rs=[r for r in rows if r['arm']==arm];lines.append(f"| {arm} | {sum(r['bytes'] for r in rs)} | {sum(r['solve_seconds'] for r in rs):.3f} |")
        lines.append('')
        for x in comparisons:
            lines.append(f"{x['challenger']} 对 {x['baseline']}：{x['outcomes']}；几何平均提速比变化 {(x['geomean_ratio']-1)*100:+.6f}%；采用条件 {x['gate']}。")
            for row in x['paired']:
                if row['outcome']=='loss':lines.append(f"退步 case{row['case']:03}/{row['cores']}核：{row['baseline']}→{row['challenger']} cycles。")
        lines.append('')
    assert all(r['replay_equal'] for r in allrows)
    summary['audit']=dict(runs=len(allrows),search_slots=sum(r['slots'] for r in allrows),search_calls=sum(r['official_calls'] for r in allrows),cache_hits=sum(r['cache_hits'] for r in allrows),final_replays=len(allrows),full100=False)
    for rel,h in c['plans'].items():assert sha((ROOT/rel).read_bytes())==h
    for name,h in c['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h,name
    verify();write_json(OUT/'summary.json',summary)
    with (OUT/'all_rows.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
    lines += ['## 口径与限制','','完整方案/评价/逐候选轨迹均保留；官方最终回放绕过缓存。搜索时间含候选准备和诊断，固定单核生成与最终回放另列，服务器并发下的时间不代表串行显著性能优势。五点为逐case固定T1/Tk算术均值，两套样本不可混为全量成绩。',json.dumps(summary['audit'],ensure_ascii=False)]
    target=ROOT/'审查/问题二初解与J同预算对照_r03.md';assert not target.exists();target.write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({p:[{k:v for k,v in x.items() if k!='paired'} for x in summary[p]['comparisons']] for p in PHASES},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','run','report']);p.add_argument('--phase',choices=list(PHASES));p.add_argument('--case',type=int);a=p.parse_args()
    {'freeze':freeze,'run':lambda:run(a.phase,a.case),'report':report}[a.action]()
