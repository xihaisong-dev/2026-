"""Audit the frozen component-routing / budget-position ablation."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from q1_io import ROOT, sha, write_json
from q1_seed_campaign import CASES
from q1_seed_report import analyze, paired

DEVELOPMENT=set(CASES)
EXTRA={'case_006','case_040','case_090','case_097'}
BIG={'case_028','case_063','case_067','case_085','case_097'}
VARIANTS=['shared_region','component_guard','component_slot']


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def audit(folder):
    checked,pairs=analyze(folder)
    summary=load(folder/'summary.json');rows=summary['runs']
    assert len(rows)==summary['expected_runs']
    assert len({(r['case'],r['cores'],r['seed'],r['config']) for r in rows})==len(rows)
    for name,digest in summary['code_sha256'].items():
        assert sha((folder/'source_snapshot'/name).read_bytes())==digest
    baseline={(r['case'],r['cores'],r['seed']):r for r in rows if r['config']=='shared_region'}
    stats={}
    def where(r):return folder/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}"
    for r in rows:stats[r['case'],r['cores'],r['seed'],r['config']]=load(where(r)/'search.json')
    gates={};fallbacks=[];observations=[];structural_rows=[]
    for v in VARIANTS[1:]:
        rr=[r for r in rows if r['config']==v];gates[v]=dict(Counter(stats[r['case'],r['cores'],r['seed'],v]['structural_seed_stats'].get('gate') for r in rr))
        for r in rr:
            s=stats[r['case'],r['cores'],r['seed'],v];info=s['structural_seed_stats'];b=baseline[r['case'],r['cores'],r['seed']]
            assert info['evaluated']<=1
            sig=lambda t:[(x['candidate'],x['makespan'],x['added_copy_bytes']) for x in t['evaluations']]
            same=None
            if not info['evaluated']:
                same=sig(s)==sig(stats[r['case'],r['cores'],r['seed'],'shared_region']) and load(where(r)/'plan.json')==load(where(b)/'plan.json')
                fallbacks.append(same)
            for item in info['ledger']:
                if v=='component_slot':assert item['replaces_candidate'].startswith('random_')
                if item['status']=='evaluated':
                    index=item['evaluation_id'];e=s['evaluations'][index]
                    incumbent=min((x['makespan'],x['added_copy_bytes']) for x in s['evaluations'][:index])
                    improved=(e['makespan'],e['added_copy_bytes'])<incumbent
                    observations.append(item['cost_observation_applied']==improved)
            structural_rows.append(dict(case=r['case'],cores=r['cores'],seed=r['seed'],config=v,gate=info.get('gate'),structural_evaluations=info['evaluated'],fallback_trajectory_identical=same,selected=info.get('generated'),ledger=info['ledger']))
    assert all(fallbacks) and all(observations)
    groups={}
    for v in VARIANTS:
        rr=[r for r in rows if r['config']==v]
        groups[v]={}
        for label,cases in [('all',DEVELOPMENT|EXTRA),('development',DEVELOPMENT),('extension',EXTRA),('large_focus',BIG)]:
            subset=[r for r in rr if r['case'] in cases]
            if subset:
                groups[v][label]=paired(subset,baseline)
                groups[v][label]['by_core']={n:paired([r for r in subset if r['cores']==n],baseline) for n in sorted({r['cores'] for r in subset})}
    return dict(groups=groups,validation=checked['validation'],gates=gates,unscored_fallbacks=len(fallbacks),all_unscored_fallbacks_identical=all(fallbacks),all_probe_observations_match_improvement=all(observations),structural_rows=structural_rows,regressions=checked['regressions'],score_calls=checked['score_calls'],reference_hits=checked['reference_hits'],validation_calls=checked['validation_calls'],summary_sha256=checked['summary_sha256']),pairs,rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--primary',type=Path,required=True)
    ap.add_argument('--robustness',type=Path,required=True)
    ap.add_argument('--previous',type=Path,required=True)
    ap.add_argument('--prior',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    main_result,main_pairs,rows=audit(args.primary)
    robust,robust_pairs,rrows=audit(args.robustness)
    prior={(r['case'],int(r['cores'])):int(r['makespan']) for r in csv.DictReader(args.prior.open(encoding='utf-8-sig')) if r['config']=='shared_region'}
    matches=[r['makespan']==prior[r['case'],r['cores']] for r in rows if r['config']=='shared_region']
    assert all(matches)
    previous=load(args.previous/'summary.json')
    current_summary=load(args.primary/'summary.json')
    for key in ['source_zip_sha256','config_sha256']:
        assert previous[key]==current_summary[key]
    for name,digest in previous['input_sha256'].items():assert current_summary['input_sha256'][name]==digest
    oldcomparisons={}
    for oldname in ['seed_components','seed_combined']:
        old={(r['case'],r['cores'],r['seed']):r for r in previous['runs'] if r['config']==oldname}
        oldcomparisons[oldname]={v:paired([r for r in rows if r['config']==v and r['case'] in DEVELOPMENT],old) for v in VARIANTS[1:]}
    eligible={v:main_result['groups'][v]['development']['time_reduction_pct']>0 and main_result['groups'][v]['large_focus']['losses']==0 and robust['groups'][v]['large_focus']['losses']==0 for v in VARIANTS[1:]}
    decision=dict(eligible_for_full100_validation=eligible,formal_adopted_changed=False,recommended_stability_candidate='component_slot',beats_previous_combined=False,selection_rule='development sum time improves and no large-focus regression; not formal adoption')
    layout_regrets=[]
    old_component={(r['case'],r['cores'],r['seed']):r for r in previous['runs'] if r['config']=='seed_components'}
    for r in rows:
        key=r['case'],r['cores'],r['seed']
        if r['config']!='component_slot' or key not in old_component or r['makespan']<=old_component[key]['makespan']:continue
        stats=load(args.primary/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_component_slot"/'search.json')
        layout_regrets.append(dict(case=r['case'],cores=r['cores'],old_time=old_component[key]['makespan'],new_time=r['makespan'],old_winner=old_component[key]['best_candidate'],new_winner=r['best_candidate'],selected=stats['structural_seed_stats'].get('generated'),ranking=stats['structural_seed_stats'].get('ranked')))
    payload=dict(layout_regrets=layout_regrets,primary=main_result,robustness=robust,previous_comparisons=oldcomparisons,baseline_matches_adopted=dict(matched=sum(matches),total=len(matches)),decision=decision)
    write_json(args.output/'summary.json',payload)
    for name,data in [('paired.csv',main_pairs),('robustness.csv',robust_pairs)]:
        with (args.output/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
    lines=['# 问题一完整分量与结构预算优化验证','',
        '范围：14 图 × 2～5 核 × 3 配置 = 168 次；十图五核 × seed 1/2 × 3 配置 = 60 次，共 228 次。每次仍为 12 个评价机会（含 1 次固定单核复用），没有增加候选评价预算。原版 A 最终重放不参与选优。','',
        '两个挑战者均只有一个经结构筛选的完整分量候选，关闭分批/深度窗口。guard 在初解阶段试一次；slot 在构造原随机提案后替换一次早期普通 random 机会。未改善的结构候选不更新成本观察。门槛、实验矩阵及接受条件均先于运行固化。','',
        '## 配对结果','',
        '| 配置 | 分组 | 胜/平/负 | 时间合计下降 | 额外搬运下降 |','|---|---|---:|---:|---:|']
    for v in VARIANTS[1:]:
        for group in ['development','extension','all','large_focus']:
            a=main_result['groups'][v][group]
            lines.append(f"| {v} | {group} | {a['wins']}/{a['ties']}/{a['losses']} | {a['time_reduction_pct']:.6f}% | {a['added_reduction_pct']:.6f}% |")
    lines+=['','development 是原十图；extension 为 006/040/090/097，历史项目用过，不能声称全新盲测；large_focus 为 028/063/067/085/097。正数改善，负数退步。','',
        '## 14 图逐例平均加速比','',
        '| 核数 | 基线 | guard | slot |','|---|---:|---:|---:|','| 1 | 1 | 1 | 1 |']
    for n in range(2,6):lines.append('| '+str(n)+' | '+' | '.join(f"{main_result['groups'][v]['all']['by_core'][n]['candidate_mean_speedup']:.6f}" for v in VARIANTS)+' |')
    lines+=['','严格先计算每图固定单核/多核时间，再取算术平均。这是 14 图开发结果，不是 100 图正式成绩。','', '## 多种子与上轮对照','']
    for v in VARIANTS[1:]:
        a=robust['groups'][v]['all'];lines.append(f"- {v} 双种子五核：{a['wins']}/{a['ties']}/{a['losses']}，时间下降 {a['time_reduction_pct']:.6f}%，搬运下降 {a['added_reduction_pct']:.6f}%。")
    for old,variants in oldcomparisons.items():
        for v,a in variants.items():lines.append(f"- {v} 对上轮 {old}（相同十图四核数组合）：{a['wins']}/{a['ties']}/{a['losses']}，时间下降 {a['time_reduction_pct']:.6f}%，搬运下降 {a['added_reduction_pct']:.6f}%。")
    lines+=['','## 审计与限制','',f"- 基线与 v18 一致 {sum(matches)}/{len(matches)}；228 份最终方案全部通过原版 A 的时间、搬运、时间线、峰值和 Step3 核验。完整评分 {main_result['score_calls']+robust['score_calls']} 次、固定单核引用 {main_result['reference_hits']+robust['reference_hits']} 次、最终复核 {main_result['validation_calls']+robust['validation_calls']} 次；单元测试另计。",
        f"- 无结构评分时，完整候选序列及最终计划与基线一致：{main_result['unscored_fallbacks']+robust['unscored_fallbacks']} 组；所有实际结构评分至多 1 次，成本观察仅在官方字典序目标改善时写入。四档基础粒度均尝试。",
        '- 原始张量并集超过缓存不是活跃峰值超过缓存。此门槛只用于保守地回到原算法，可能错过好方案；三个布局中的静态排序也可能选错，故必须保留失败结果并在更多图上验证。',
        '- 即使替换普通 random，也不保证后续候选完全不变：新父解和官方成本观察会改变搜索；不能声称对所有图无退化。',
        '- 所有 228 次都在同一服务器运行，主实验 12 worker、稳健性 4 worker 同时执行。日志与 server_execution.json 给出真实耗时；未做串行运行耗时因果对照，不能用秒数差代表调度 cycles 收益。','', '## 退步逐组','']
    negatives=main_result['regressions']+robust['regressions']
    if not negatives:lines.append('相对本轮基线，所测配置未观察到退步。该结论仅覆盖上述矩阵。')
    for r in negatives:lines.append(f"- {r['case']} / {r['cores']} 核 / seed {r['seed']} / {r['config']}：{r['baseline_makespan']} → {r['makespan']}，时间变化 {-r['time_reduction_pct']:+.6f}%。")
    lines+=['','## 单候选筛选的代价','',
        '不能把这一轮称为相对所有已有方案更快：slot 在相同十图上的总时间比上轮组合慢 0.221386%，比上轮完整分量三布局版本慢 0.012373%。本轮主要修复了相对原基线的退步风险。',
        'case_077 二/三/四核：上轮完整分量版本的赢家均为 LPT，新下界排序只选 Pipe 布局，错过了更好的初解。Pipe 工作量下界可以用于排除必然过慢方案，却不足以可靠排序实际 Makespan；它未完整体现数据搬运重叠、核内排程和缓存代价。',
        'case_017 的部分差距还来自后续 directed_split 路径不同，不能把全部损失归因于初解类型。因此下一步宜单独验证：首个分量方案确实改善后，才在固定总预算内给另一种结构不同的布局机会；不预设这一机制一定有效。',
        '', '## 后续决策','',json.dumps(decision,ensure_ascii=False), '',
        '满足条件仅表示可继续固定规则的全量同预算验证；本轮不改正式默认或阶段门禁。若静态只选一个布局损失收益，应先诊断它与上轮实际优胜布局的差距，不能把事后逐例挑最优包装为可部署算法。']
    (ROOT/'审查/问题一分量预算优化验证_20260924.md').write_bytes(('\n'.join(lines)+'\n').encode('utf8'))
    print(json.dumps({v:{k:a for k,a in main_result['groups'][v]['all'].items() if k in ['count','wins','ties','losses','time_reduction_pct','added_reduction_pct']} for v in VARIANTS[1:]},ensure_ascii=False))


if __name__=='__main__':main()
