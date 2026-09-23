"""Audit conditional second-layout experiments and paired official results."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from q1_io import sha, write_json
from q1_seed_report import paired
from q1_seed_campaign import CASES

BIG = {'case_028','case_063','case_067','case_085','case_097'}

def load(path):
    return json.loads(path.read_text(encoding='utf8'))

def key(row):
    return row['case'], row['cores'], row['seed']

def folder(root, row):
    return root/f"{row['case']}_{row['cores']}cores_seed{row['seed']}_{row['config']}"

def signature(stats):
    return [(r['candidate'], r['makespan'], r['added_copy_bytes']) for r in stats['evaluations']]

def audit(root, prior):
    summary = load(root/'summary.json')
    assert summary['completed'] and not summary['failures']
    rows = summary['runs']
    assert len(rows) == summary['expected_runs']
    assert len({key(r)+(r['config'],) for r in rows}) == len(rows)
    for name, digest in summary['code_sha256'].items():
        assert sha((root/'source_snapshot'/name).read_bytes()) == digest
    baseline = {key(r):r for r in rows if r['config']=='component_slot'}
    old_summary=load(prior/'summary.json')
    for field in ['source_zip_sha256','config_sha256']:assert summary[field]==old_summary[field]
    for name,digest in summary['input_sha256'].items():assert digest==old_summary['input_sha256'][name]
    old = {key(r):r for r in old_summary['runs'] if r['config']=='component_slot'}
    table=[]; probes=[]; routing_outcomes=Counter(); unchanged=0; unlocked=0; second_scored=0; second_improved=0
    for row in rows:
        path=folder(root,row);stats=load(path/'search.json')
        for name,digest in row['artifacts'].items():assert sha((path/name).read_bytes())==digest
        assert all(load(path/'verification.json').values()) and row['verification_passed']
        assert row['evaluated_opportunities']==len(stats['evaluations'])==12
        assert row['full_score_calls']==11 and row['fixed_reference_hits']==1
        assert stats['protected_grain_attempts']==[.5,1.,2.,.25]
        assert abs(row['speedup']-row['single_makespan']/row['makespan'])<1e-12
        assert (row['makespan'],row['added_copy_bytes']) == min((e['makespan'],e['added_copy_bytes']) for e in stats['evaluations'])
        if row['config']=='component_slot':
            oldrow=old[key(row)];oldpath=folder(prior,oldrow)
            for field in ['makespan','added_copy_bytes','single_makespan']:assert row[field]==oldrow[field]
            assert load(path/'plan.json')==load(oldpath/'plan.json')
            assert signature(stats)==signature(load(oldpath/'search.json'))
            continue
        base=baseline[key(row)];basepath=folder(root,base)
        info=stats['structural_seed_stats'];ledger=info['ledger']
        routing_outcomes['gate:'+info.get('gate','unknown')]+=1
        if info.get('followup_skip_reason'):routing_outcomes[info['followup_skip_reason']]+=1
        if len(ledger)>1:routing_outcomes['second:'+ledger[1]['status']]+=1
        actual=[x for x in ledger if x['status']=='evaluated']
        assert len(actual)==info['evaluated']<=2
        assert len(ledger)<=2
        if ledger:
            first=ledger[0]
            improved=first['status']=='evaluated' and stats['evaluations'][first['evaluation_id']]['makespan']<first['incumbent_makespan']
            assert info['followup_unlocked']==improved
            unlocked+=improved
            if len(ledger)>1:assert improved
        for item in actual:
            index=item['evaluation_id'];evaluation=stats['evaluations'][index]
            incumbent=min((e['makespan'],e['added_copy_bytes']) for e in stats['evaluations'][:index])
            assert item['incumbent_makespan']==incumbent[0]
            assert item['cost_observation_applied']==((evaluation['makespan'],evaluation['added_copy_bytes'])<incumbent)
            if item['opportunity']=='ordinary_random':assert item['replaces_candidate'].startswith('random_')
            else:
                assert item['opportunity']=='equivalent_duplicate'
                assert 0<=item['replaced_equivalent_evaluation_id']<index
            probes.append(dict(case=row['case'],cores=row['cores'],seed=row['seed'],**item,
                               makespan=evaluation['makespan']))
        did_second=any(x['probe_index']==2 for x in actual)
        if did_second:
            second_scored+=1
            second=next(x for x in actual if x['probe_index']==2)
            second_improved+=stats['evaluations'][second['evaluation_id']]['makespan']<second['incumbent_makespan']
        else:
            assert signature(stats)==signature(load(basepath/'search.json'))
            assert load(path/'plan.json')==load(basepath/'plan.json')
            unchanged+=1
        table.append(dict(case=row['case'],cores=row['cores'],seed=row['seed'],baseline_makespan=base['makespan'],makespan=row['makespan'],
            baseline_speedup=base['speedup'],speedup=row['speedup'],baseline_added_bytes=base['added_copy_bytes'],added_bytes=row['added_copy_bytes'],
            time_reduction_pct=100*(base['makespan']-row['makespan'])/base['makespan'],unlocked=info.get('followup_unlocked',False),second_scored=did_second,
            winner=row['best_candidate'],skip_reason=info.get('followup_skip_reason','')))
    rr=[r for r in rows if r['config']=='component_followup']
    groups={}
    for name,subset in [('all',rr),('development',[r for r in rr if r['case'] in CASES]),('extension',[r for r in rr if r['case'] not in CASES]),('large_focus',[r for r in rr if r['case'] in BIG])]:
        if subset:groups[name]=paired(subset,baseline)
    by_core={n:paired([r for r in rr if r['cores']==n],baseline) for n in sorted({r['cores'] for r in rr})}
    return dict(groups=groups,by_core=by_core,routing_outcomes=dict(routing_outcomes),unlocked=unlocked,second_scored=second_scored,second_improved=second_improved,
        no_second_trajectory_identical=unchanged,baseline_prior_matches=len(baseline),all_checks_passed=True,
        score_calls=sum(r['full_score_calls'] for r in rows),reference_hits=len(rows),validation_calls=len(rows),
        summary_sha256=sha((root/'summary.json').read_bytes()),protocol_sha256=summary['protocol_sha256'],
        regressions=[r for r in table if r['makespan']>r['baseline_makespan']],probes=probes,
        opportunity_counts=dict(Counter(r['opportunity'] for r in probes if r['probe_index']==2))),table,rr

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['primary','robustness','prior-primary','prior-robustness','previous','output']:ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    p,pt,rows=audit(args.primary,args.prior_primary)
    r,rt,_=audit(args.robustness,args.prior_robustness)
    assert p['protocol_sha256']==r['protocol_sha256']
    assert len(pt)==56 and len(rt)==20
    old=load(args.previous/'summary.json')['runs'];comparison={}
    for name in ['seed_components','seed_combined']:
        bb={key(x):x for x in old if x['config']==name}
        comparison[name]=paired([x for x in rows if key(x) in bb],bb)
    result=dict(primary=p,robustness=r,previous_comparisons=comparison,formal_default_changed=False,
        qualifies_for_full100=p['groups']['development']['time_reduction_pct']>0 and p['groups']['large_focus']['losses']==0)
    write_json(args.output/'summary.json',result)
    for name,rr in [('paired.csv',pt),('robustness.csv',rt)]:
        with (args.output/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rr[0]));writer.writeheader();writer.writerows(rr)
    lines=['# 问题一条件第二布局：验证结果','',
        '同一预算 12，component_slot 对照 component_followup。14 图 seed=0、2～5 核共 112 次；开发十图五核 seed=1/2 共 40 次。不是 100 图全量结果。',
        '平均加速比统一逐例 T1/Tk 取算术平均；时间合计下降采用总 cycles 加权。', '',
        '| 分组 | 胜/平/负 | 对照时间合计 | 新方案时间合计 | 时间下降 | 额外搬运下降 |','|---|---:|---:|---:|---:|---:|']
    for label,a in [('主实验',p['groups']['all']),('开发十图',p['groups']['development']),('扩展四图',p['groups']['extension']),('重点大图',p['groups']['large_focus']),('双种子',r['groups']['all'])]:
        lines.append(f"| {label} | {a['wins']}/{a['ties']}/{a['losses']} | {a['baseline_cycles']} | {a['candidate_cycles']} | {a['time_reduction_pct']:.6f}% | {a['added_reduction_pct']:.6f}% |")
    lines+=['','| 核数 | slot | followup |','|---|---:|---:|','| 1 | 1.000000 | 1.000000 |']
    for n,a in p['by_core'].items():lines.append(f"| {n} | {a['baseline_mean_speedup']:.6f} | {a['candidate_mean_speedup']:.6f} |")
    lines+=['','## 预算和实际触发','']
    for name,a in [('主实验',p),('稳健性',r)]:
        lines.append(f"- {name}：解锁 {a['unlocked']} 次，第二候选正式评分 {a['second_scored']} 次，当场降低 Makespan {a['second_improved']} 次；无第二评分的 {a['no_second_trajectory_identical']} 组完整搜索和最终方案与 slot 一致。机会来源 {a['opportunity_counts']}。")
    lines += ['',f"152 份最终原版 A 重放全部通过；{p['score_calls']+r['score_calls']} 次完整评分、152 次固定单核复用、152 次最终核验。重跑 slot 与上一轮 {p['baseline_prior_matches']+r['baseline_prior_matches']} 组轨迹和结果一致。四档基础粒度均构造；正式源码和逐份产物哈希已核验。",'', '## 退步与历史比较','']
    for x in p['regressions']+r['regressions']:lines.append(f"- {x['case']} / {x['cores']} 核 / seed {x['seed']}：{x['baseline_makespan']} → {x['makespan']}（{-x['time_reduction_pct']:+.6f}%）。")
    if not p['regressions']+r['regressions']:lines.append('本轮相对 slot 未观察到最终 Makespan 退步；搬运仍可能增加，仅限本矩阵。')
    for name,a in comparison.items():lines.append(f"- 与上一轮 {name} 在相同十图 seed=0 四核数比较：{a['wins']}/{a['ties']}/{a['losses']}，总时间下降 {a['time_reduction_pct']:.6f}%，搬运下降 {a['added_reduction_pct']:.6f}%。")
    lines+=['','## 决策与限制','',f"满足预定全量验证候选条件：{result['qualifies_for_full100']}；正式默认未变。",'第二布局也可能改变后续成本观察和父解；回收重复机会不能保证所有图绝不退步。没有普通随机/重复机会时不强行评分；分量门槛及静态排序仍可能错过优质方案。', '三类原始分量布局引用用户参考工程；本轮新增条件解锁和预算管理，不声称原始布局原创。', '协议、哈希及命令见运行目录和交接。服务器并行负载下的求解秒数不能作为因果性能比较；提交门禁与人工接收未运行。']
    (args.output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({name:obj['groups']['all'] for name,obj in [('primary',p),('robustness',r)]},ensure_ascii=False))

if __name__=='__main__':main()
