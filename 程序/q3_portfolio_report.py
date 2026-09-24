"""Local verification and descriptive pilot summary; no formal gate approval."""
import argparse, gzip, json
from pathlib import Path
from statistics import mean
from q1_io import ROOT, PROCESSED, sha, write_json
from q3_solver import load, evaluate, audit, audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text());done=json.loads((a.run/'completion.json').read_text())
    assert done['complete'] and done['count']==32
    for f,h in c['sources'].items():assert sha((ROOT/'程序'/f).read_bytes())==h
    freeze=json.loads((ROOT/'审查/证据/20260924-A-q3/baseline-freeze-r02.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/freeze['baseline']/f).read_bytes())==h for f,h in freeze['files'].items())
    params=json.loads((ROOT/'审查/证据/20260924-A-q3/parameter-freeze-before-r03.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/f).read_bytes())==h for f,h in params.items())
    rows=json.loads((a.run/'progress.json').read_text()); lookup={(r['case'],r['cores'],r['mode']):r for r in rows}
    for row in rows:
        folder=a.run/f"case_{row['case']:03}/{row['cores']}/{row['mode']}"
        search=json.loads((folder/'search.json').read_text())
        assert search['replay_equal'] and len(search['evaluations'])<=24
        assert len({e['plan_sha256'] for e in search['evaluations']})==len(search['evaluations'])
        assert row['makespan']<=row['baseline'] and row['invalid']==0 and 0<=row['hit_rate']<=1
    for f in a.run.glob('case_*/*/*/result.json.gz'):audit_cache(json.load(gzip.open(f,'rt',encoding='utf-8')))
    settings,delay,cache,_=load();replays=[]
    # Verify the budget stress case and strongest validation results.
    validation_pairs={tuple(x) for x in c['validation']}
    winners=[r for r in rows if r['mode']=='adaptive' and r['makespan']<r['baseline'] and (r['case'],r['cores']) in validation_pairs]
    targets=[(58,2,'adaptive')]
    if winners:targets.append((min(winners,key=lambda r:r['makespan']/r['baseline'])['case'],min(winners,key=lambda r:r['makespan']/r['baseline'])['cores'],'adaptive'))
    rs=[r for r in rows if r['mode']=='reserved' and (r['case'],r['cores']) in validation_pairs]
    winner=min(rs,key=lambda r:r['makespan']/r['baseline'])
    targets.append((winner['case'],winner['cores'],'reserved'))
    for case,n,mode in dict.fromkeys(targets):
        folder=a.run/f'case_{case:03}/{n}/{mode}'
        raw=json.loads((PROCESSED/f'data/case_{case:03}.json').read_text(encoding='utf-8'));plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
        r=evaluate(raw,plan,settings,delay,cache);saved=json.load(gzip.open(folder/'result.json.gz','rt',encoding='utf-8'))
        assert json.loads(json.dumps(r))==saved
        replays.append(dict(case=case,cores=n,makespan=r['makespan'],checks=audit(raw,plan,r,settings,delay)))
    stats={}
    for split in ['discovery','validation']:
        stats[split]={}
        for mode in c['modes']:
            rs=[lookup[i,n,mode] for i,n in c[split]]
            stats[split][mode]=dict(wins=sum(r['makespan']<r['baseline'] for r in rs),mean_reduction=mean(1-r['makespan']/r['baseline'] for r in rs),calls=sum(r['calls'] for r in rs),seconds=sum(r['seconds'] for r in rs))
    v=stats['validation']; versus={m:sum(lookup[i,n,'adaptive']['makespan']<lookup[i,n,m]['makespan'] for i,n in c['validation']) for m in ['beam','reserved','fixed']}
    gate=v['adaptive']['wins']>=2 and v['adaptive']['mean_reduction']>=.002 and versus['beam']>=2 and all(v['adaptive']['mean_reduction']>v[m]['mean_reduction'] for m in versus)
    summary=dict(stats=stats,validation_wins_vs=versus,promotion_criteria_met=gate,expanded=False,formal_gate='NOT_RUN')
    write_json(a.run/'summary.json',summary)
    write_json(a.run/'local_verification.json',dict(fifo_ledgers=32,replays=replays,baseline_files_unchanged=len(freeze['files']),parameter_files_unchanged=len(params)))
    lines=['# 问题三预算保留与缓存-ASAP组合试验 r05','',f'预声明扩量条件满足：{gate}。未扩量、未提交或派稿，正式门禁NOT_RUN。','',
        '四方法同为最多24个唯一候选：beam为r04旧方法；reserved为纯ASAP原方案保留16次；fixed为ASAP和缓存候选轮转；adaptive为相同原方案保留后按观察收益选族。先前轨迹只用于提出候选，接受以官方精确重放为准。','',
        '|案例/核数|500组基线|旧beam|保留预算ASAP|固定组合|收益组合|','|---|---:|---:|---:|---:|---:|']
    for i,n in c['discovery']+c['validation']:
        vals=[lookup[i,n,m]['makespan'] for m in c['modes']]
        lines.append(f"|{i}/{n}|{lookup[i,n,'beam']['baseline']}|"+'|'.join(map(str,vals))+'|')
    lines+=['','前4例为发现组，后4例为新算法验证组；原始数据均参与过基线，不能称未见数据。','']
    for split,ss in stats.items():
        for mode,x in ss.items():lines.append(f"- {split}/{mode}：改善{x['wins']}例，平均周期降幅{x['mean_reduction']:.6%}，实际评估{x['calls']}次，累计作业耗时{x['seconds']:.2f}秒。")
    lines+=['',f'验证组adaptive相对其他方法胜例数：{versus}。',
        '历史最好必须单独比较：case49/4核74890；case58/2核2257877；case67/2核31763533；case98/4核52957。对500组有收益不等于刷新历史最好。',
        '',f"校验：32份FIFO账本，{len(replays)}份完整跨平台重放，3005份基线与198份参数分析文件哈希未变。所有终选方案在服务器审计内存、依赖、同步与流量。",
        '', '局限：保留16次不能保证原方案24个候选都被搜索；观察收益可能重复，不能等同独立边际收益。固定组合与收益组合的对照用于检验预算规则是否有增益。预声明小样本条件不代表统计显著性或全局最优。按需生成与区间缓存加速会影响用时，因此运行时间仅是整个实现的实际成本，不能单独归因于搜索规则。']
    lines+=['','实现加速单独保留：q3_asap_accelerated.solve使用r04相同搜索规则与同序惰性候选。case12的11个候选和case49的24个候选完整一致；case49完整搜索的24次评估记录、最终方案和所有官方结果字段均一致。本机case49单次候选生成5.71秒→1.03秒，完整加速搜索22.00秒；未进行同机完整新旧计时对照，不推断整体倍数。详见审查/证据/20260924-A-q3/portfolio-r05-tests.json。']
    (ROOT/'审查/问题三预算分配与组合搜索_r05.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
