"""Local verification and descriptive pilot summary; no formal gate approval."""
import argparse, gzip, json
from pathlib import Path
from statistics import mean
from q1_io import ROOT, PROCESSED, sha, write_json
from q3_solver import load, evaluate, audit, audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text());done=json.loads((a.run/'completion.json').read_text())
    assert done['complete'] and done['count']==30
    for f,h in c['sources'].items():assert sha((ROOT/'程序'/f).read_bytes())==h
    freeze=json.loads((ROOT/'审查/证据/20260924-A-q3/baseline-freeze-r02.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/freeze['baseline']/f).read_bytes())==h for f,h in freeze['files'].items())
    params=json.loads((ROOT/'审查/证据/20260924-A-q3/parameter-freeze-before-r03.json').read_text(encoding='utf-8'))
    assert all(sha((ROOT/f).read_bytes())==h for f,h in params.items())
    rows=json.loads((a.run/'progress.json').read_text()); lookup={(r['case'],r['cores'],r['mode']):r for r in rows}
    from q2_solver import owner_of
    for row in rows:
        folder=a.run/f"case_{row['case']:03}/{row['cores']}/{row['mode']}"
        search=json.loads((folder/'search.json').read_text())
        assert search['replay_equal'] and len(search['evaluations'])<=24
        assert len({e['plan_sha256'] for e in search['evaluations']})==len(search['evaluations'])
        assert row['makespan']<=row['baseline'] and row['invalid']==0 and 0<=row['hit_rate']<=1
        if row['mode']!='control':
            source=ROOT/freeze['baseline']/f"case_{row['case']:03}/{row['cores']}/case_{row['case']:03}_multicore_res.json"
            seed=json.loads(source.read_text());plan=json.loads((folder/'plan.json').read_text())
            assert seed['node_to_subgraph']==plan['node_to_subgraph'] and owner_of(seed)==owner_of(plan)
    for f in a.run.glob('case_*/*/*/result.json.gz'):audit_cache(json.load(gzip.open(f,'rt',encoding='utf-8')))
    settings,delay,cache,_=load();replays=[]
    # Include actual beam winner if available, and the root-preservation stress case.
    validation_pairs={tuple(x) for x in c['validation']}
    winners=[r for r in rows if r['mode']=='beam' and r['makespan']<r['baseline'] and (r['case'],r['cores']) in validation_pairs]
    targets=[(12,5,'beam'),(58,2,'beam')]
    if winners:targets.append((min(winners,key=lambda r:r['makespan']/r['baseline'])['case'],min(winners,key=lambda r:r['makespan']/r['baseline'])['cores'],'beam'))
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
    v=stats['validation']; versus={m:sum(lookup[i,n,'beam']['makespan']<lookup[i,n,m]['makespan'] for i,n in c['validation']) for m in ['single','control']}
    gate=v['beam']['wins']>=3 and v['beam']['mean_reduction']>=.002 and all(versus[m]>=2 and v['beam']['mean_reduction']>v[m]['mean_reduction'] for m in versus)
    summary=dict(stats=stats,validation_wins_vs=versus,promotion_criteria_met=gate,expanded=False,formal_gate='NOT_RUN')
    write_json(a.run/'summary.json',summary)
    write_json(a.run/'local_verification.json',dict(fifo_ledgers=30,replays=replays,baseline_files_unchanged=len(freeze['files']),parameter_files_unchanged=len(params)))
    lines=['# 问题三 ASAP 式流水线压缩试验 r04','',f'扩量条件满足：{gate}。本轮未扩展500组，未提交或派稿；正式门禁 NOT_RUN。','',
        '方法：只在合法子图顺序层面压缩关键管线队首等待。原核内前移独立子图或生产子图；官方内核调度、FIFO与带宽规则不变。single固定根邻域；beam保留根与当前最好分支；control为r03无分类迭代。每项最多24个唯一候选，耗尽时提前停止。','',
        '|案例/核数|500组基线|固定根ASAP|保留根分支ASAP|原方法对照|','|---|---:|---:|---:|---:|']
    for i,n in c['discovery']+c['validation']:
        lines.append(f"|{i}/{n}|{lookup[i,n,'beam']['baseline']}|{lookup[i,n,'single']['makespan']}|{lookup[i,n,'beam']['makespan']}|{lookup[i,n,'control']['makespan']}|")
    lines += ['', '发现组为前4例，新算法验证组为后6例；全部原始算例已参与过基线，不称独立未见数据。','']
    for split,ss in stats.items():
        for mode,x in ss.items():lines.append(f"- {split}/{mode}：改善{x['wins']}例，平均周期降幅{x['mean_reduction']:.6%}，实际评估{x['calls']}次，累计作业耗时{x['seconds']:.2f}秒。")
    lines+=['',f'验证组beam相对single/control的胜例数：{versus}。',
        '历史最好对照：case12/5核已达到11971；case5/5核47731；case67/2核31763533；case58/2核2257877。达到相同周期不能声称新收益。',
        '',f"校验：30份FIFO账本，{len(replays)}份完整跨平台重放，3005份基线文件与198份参数分析文件哈希未变。每个终选方案在服务器审计依赖、同步、流量和内存。",
        '', '局限：只搜索同核前移，尚未覆盖跨核移动、切图调整、非关键等待或多步暂时恶化的路径。关键图使用已观察时长，空闲窗口不是反事实节省量；低预算失败不能证明该方向无效。']
    (ROOT/'审查/问题三ASAP流水线压缩试验_r04.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
