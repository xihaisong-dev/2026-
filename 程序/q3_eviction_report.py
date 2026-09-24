"""Local verification and descriptive pilot summary; no formal gate approval."""
import argparse, gzip, json
from pathlib import Path
from statistics import mean
from q1_io import ROOT, PROCESSED, sha, write_json
from q3_solver import load, evaluate, audit, audit_cache

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    c=json.loads((a.run/'contract.json').read_text());done=json.loads((a.run/'completion.json').read_text())
    assert done['complete'] and done['count']==3*(len(c['discovery'])+len(c['validation']))
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
        seed_path=ROOT/freeze['baseline']/f"case_{row['case']:03}/{row['cores']}/case_{row['case']:03}_multicore_res.json"
        seed=json.loads(seed_path.read_text());plan=json.loads((folder/'plan.json').read_text())
        assert seed['node_to_subgraph']==plan['node_to_subgraph'] and owner_of(seed)==owner_of(plan)
        for e in search['evaluations']:
            w=e['move']['witness'];assert w['fill_time']<=w['eviction_time']<=w['read_time'] and w['eviction_event']<w['miss_event']
    for f in a.run.glob('case_*/*/*/result.json.gz'):audit_cache(json.load(gzip.open(f,'rt',encoding='utf-8')))
    mechanisms=[]
    for row in rows:
        folder=a.run/f"case_{row['case']:03}/{row['cores']}/{row['mode']}"
        search=json.loads((folder/'search.json').read_text())
        accepted=[e for e in search['evaluations'] if e['accepted']]
        if not accepted:continue
        e=accepted[-1]['move']['witness']
        baseline=ROOT/freeze['baseline']/f"case_{row['case']:03}/{row['cores']}/selected_l2.json.gz"
        def read_group(result):
            groups={(c['core_id'],o['op_id']):o['subgraph_id'] for c in result['per_core_timeline'] for o in c['ops']}
            return [dict(time=z['time'],event=z['event'],op=z['op_id'],core=z['core_id']) for z in result['cache_events'] if z['event'] in ['hit','miss'] and z['tensor_id']==e['tensor'] and groups[z['core_id'],z['op_id']]==e['consumer_group']]
        before=json.load(gzip.open(baseline,'rt'));after=json.load(gzip.open(folder/'result.json.gz','rt'))
        mechanisms.append(dict(case=row['case'],cores=row['cores'],mode=row['mode'],witness=e,before=read_group(before),after=read_group(after),makespan_before=before['makespan'],makespan_after=after['makespan'],hit_rate_before=before['cache_stats']['hit_rate'],hit_rate_after=after['cache_stats']['hit_rate'],added_before=before['data_movement_bytes']['added_copy_bytes'],added_after=after['data_movement_bytes']['added_copy_bytes']))
    write_json(a.run/'mechanism_comparison.json',mechanisms)
    settings,delay,cache,_=load();replays=[]
    targets=[]
    for split in ['discovery','validation']:
        rs=[r for r in rows if [r['case'],r['cores']] in c[split]]
        winner=min(rs,key=lambda r:r['makespan']/r['baseline'])
        targets.append((winner['case'],winner['cores'],winner['mode']))
    targets.append((*c['validation'][0],'source'))
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
    v=stats['validation']; versus={m:sum(lookup[i,n,'joint']['makespan']<lookup[i,n,m]['makespan'] for i,n in c['validation']) for m in ['consumer','source']}
    gate=v['joint']['wins']>=3 and v['joint']['mean_reduction']>=.002 and all(versus[m]>=2 and v['joint']['mean_reduction']>v[m]['mean_reduction'] for m in versus)
    summary=dict(stats=stats,validation_wins_vs=versus,promotion_criteria_met=gate,expanded=False,formal_gate='NOT_RUN')
    historical={}
    for name in ['20260924-A-q3-explore-r01','20260924-A-q3-research-r02','20260924-A-q3-adaptive-r03','20260924-A-q3-asap-r04','20260924-A-q3-portfolio-r05']:
        for f in (ROOT/'图表/runs'/name).rglob('metrics.json'):
            old=json.loads(f.read_text())
            if not all(k in old for k in ['case','cores','makespan']):continue
            pair=(old['case'],old['cores'])
            if pair not in historical or old['makespan']<historical[pair]['makespan']:historical[pair]=dict(makespan=old['makespan'],source=str(f.relative_to(ROOT)))
    comparisons=[]
    for i,n in c['discovery']+c['validation']:
        base=lookup[i,n,'joint']['baseline'];prior=historical.get((i,n),dict(makespan=base,source='frozen full-r02'))
        if prior['makespan']>base:prior=dict(makespan=base,source='frozen full-r02')
        comparisons.append(dict(case=i,cores=n,prior=prior,new_best=min(lookup[i,n,m]['makespan'] for m in c['modes'])))
    summary['historical_comparison']=comparisons
    write_json(a.run/'summary.json',summary)
    write_json(a.run/'local_verification.json',dict(fifo_ledgers=done['count'],replays=replays,baseline_files_unchanged=len(freeze['files']),parameter_files_unchanged=len(params)))
    lines=['# 问题三关键再读与淘汰来源干预 r07','',f'新验证门槛满足：{gate}。未扩量、未提交或派稿；正式门禁NOT_RUN。','',
        '选择仅依据冻结五核轨迹中的一条关键链、直接淘汰事件及三臂合法候选可用性。不是随机代表样本，也不是未见原始数据。消费者、淘汰来源的单步移动以及联合移动均在原核内完成。每臂固定起点，最多24个不同候选，官方重放后保留不劣方案。','',
        '|组别/案例/核数|冻结起点|消费者前移|来源后移|联合调整|','|---|---:|---:|---:|---:|']
    for split in ['discovery','validation']:
        for i,n in c[split]:
            vals=[lookup[i,n,m]['makespan'] for m in c['modes']]
            lines.append(f"|{split}/{i}/{n}|{lookup[i,n,'joint']['baseline']}|"+'|'.join(map(str,vals))+'|')
    lines+=['','统计：','']
    for split,ss in stats.items():
        for mode,x in ss.items():lines.append(f"- {split}/{mode}：改善{x['wins']}例，平均周期降幅{x['mean_reduction']:.6%}，实际评估{x['calls']}次，累计作业耗时{x['seconds']:.2f}秒。")
    lines+=['',f'验证组joint相对两单步胜例数：{versus}。',
        '',f"校验：{done['count']}份FIFO账本，{len(replays)}份完整跨平台重放，原3005份基线与198份参数分析文件未变。所有终选方案在服务器检查内存、依赖、同步与流量。",
        '', '事件证据只指实际轨迹中直接触发淘汰的插入，不证明移动该来源一定保留张量；更早的插入也贡献了容量压力。候选目标事件只提示时机，接受由完整官方重放决定。消费者组可能多次读取同一张量，因此记录其全部读事件，不能凭生成op id直接断言原miss转hit。此次失败也不能排除跨核移动、分组改变或扩大联合区域后有收益。']
    lines+=['','历史最好对照（不同预算产生，仅作存量成绩核对，不作公平算法对擂）：']
    for x in comparisons:lines.append(f"- case{x['case']}/{x['cores']}核：此前{x['prior']['makespan']}，本轮三臂最好{x['new_best']}。")
    lines+=['','筛选范围：100个五核方案中20例在所抽取关键链上有可关联的再读事件，12例满足三臂合法候选条件。原发现池仅3例，原4+4检查如实停止；在评估任何候选前记录修订，采用3发现+4验证，验证门槛未变。详见独立screen目录contract及selection-amended。',
        '上述20例已排除消费者与直接淘汰来源属于同一子图、或无法归属子图的事件；并非说其余80图没有关键未命中。只抽取一条关键链及同核整子图移动的限制也会排除其他潜在机会。',
        'metrics中accepted_rounds为沿用字段名，实际计数为接受候选次数；本轮每臂只有一个固定起点邻域，不是多轮迭代。']
    (ROOT/'审查/问题三关键再读与淘汰来源干预_r07.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
