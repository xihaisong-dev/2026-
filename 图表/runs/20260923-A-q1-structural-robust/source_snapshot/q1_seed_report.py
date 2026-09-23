"""Summarize paired structural-seed ablations; never pool unequal core subsets."""
import argparse
import csv
import json
from pathlib import Path
import statistics
from q1_io import ROOT, sha, write_json
from q1_seed_campaign import CASES, VARIANTS

OLD = set(CASES[:5])


def paired(rows, baseline):
    differences=[]
    for row in rows:
        base=baseline[row['case'],row['cores'],row['seed']]
        differences.append((base,row))
    before=sum(a['makespan'] for a,b in differences)
    after=sum(b['makespan'] for a,b in differences)
    bytes0=sum(a['added_copy_bytes'] for a,b in differences)
    bytes1=sum(b['added_copy_bytes'] for a,b in differences)
    return dict(count=len(rows),wins=sum(b['makespan']<a['makespan'] for a,b in differences),
                ties=sum(b['makespan']==a['makespan'] for a,b in differences),
                losses=sum(b['makespan']>a['makespan'] for a,b in differences),
                baseline_cycles=before,candidate_cycles=after,time_reduction_pct=100*(before-after)/before,
                baseline_added_bytes=bytes0,candidate_added_bytes=bytes1,
                added_reduction_pct=100*(bytes0-bytes1)/bytes0 if bytes0 else None,
                baseline_mean_speedup=statistics.mean(a['speedup'] for a,b in differences),
                candidate_mean_speedup=statistics.mean(b['speedup'] for a,b in differences),
                mean_solve_seconds=statistics.mean(b['solve_seconds'] for a,b in differences),
                median_solve_seconds=statistics.median(b['solve_seconds'] for a,b in differences),
                max_solve_seconds=max(b['solve_seconds'] for a,b in differences),
                over_600=sum(b['solve_seconds']>600 for a,b in differences))


def analyze(folder):
    summary=json.loads((folder/'summary.json').read_text(encoding='utf8'))
    assert summary['completed'] and not summary['failures']
    rows=summary['runs'];baseline={(r['case'],r['cores'],r['seed']):r for r in rows if r['config']=='shared_region'}
    result=dict(summary_sha256=sha((folder/'summary.json').read_bytes()),count=len(rows),
                wall_seconds=summary['wall_seconds'],variants={},validation={},regressions=[],
                validation_calls=sum(r['verification_calls'] for r in rows),
                score_calls=sum(r['full_score_calls'] for r in rows),
                reference_hits=sum(r['fixed_reference_hits'] for r in rows))
    all_prefix=True;all_grain=True;failed_artifacts=[];paired_rows=[]
    for row in rows:
        key=(row['case'],row['cores'],row['seed'])
        path=folder/f"{row['case']}_{row['cores']}cores_seed{row['seed']}_{row['config']}"
        for name,h in row['artifacts'].items():
            if sha((path/name).read_bytes())!=h:failed_artifacts.append(str(path/name))
        stats=json.loads((path/'search.json').read_text(encoding='utf8'))
        bp=folder/f"{row['case']}_{row['cores']}cores_seed{row['seed']}_shared_region"/'search.json'
        base_stats=json.loads(bp.read_text(encoding='utf8'))
        initial=lambda s:[(r['candidate'],r['plan_sha256'],r['status']) for r in s['proposal_ledger']
                          if r['candidate'] in {'single_task','greedy','multilevel'}]
        all_prefix &= initial(stats)==initial(base_stats)
        all_grain &= stats['protected_grain_attempts']==[.5,1.,2.,.25]
        base=baseline[key]
        winner=min(base_stats['evaluations'],key=lambda x:(x['makespan'],x['added_copy_bytes']))
        bplan=json.loads((bp.parent/'plan.json').read_text(encoding='utf8'))
        import hashlib
        winner_hash=hashlib.sha256(json.dumps(bplan,sort_keys=True).encode()).hexdigest()
        pair={k:row[k] for k in ['case','cores','seed','config','makespan','speedup','added_copy_bytes','solve_seconds','best_candidate','structural_evaluations']}
        pair.update(baseline_makespan=base['makespan'],time_reduction_pct=100*(base['makespan']-row['makespan'])/base['makespan'],
                    baseline_added_bytes=base['added_copy_bytes'],
                    structural_best=min((r['makespan'] for r in stats['evaluations'] if r['candidate'].startswith('structural_')),default=None),
                    max_unique_structural=stats['structural_seed_stats'].get('limit',0),
                    baseline_best_candidate=winner['candidate'],
                    baseline_winner_evaluated=any(r.get('plan_sha256')==winner_hash and r['status']=='evaluated' for r in stats['proposal_ledger']),
                    same_label_candidate_times=json.dumps([r['makespan'] for r in stats['evaluations'] if r['candidate']==winner['candidate']]))
        paired_rows.append(pair)
        if row['config']!='shared_region' and row['makespan']>base['makespan']:result['regressions'].append(pair)
    for name in sorted({r['config'] for r in rows}):
        rr=[r for r in rows if r['config']==name]
        result['variants'][name]={group:paired([r for r in rr if group=='all' or (r['case'] in OLD)==(group=='old_five')],baseline)
                                 for group in ['all','old_five','counterexamples']}
        result['variants'][name]['by_core']={n:paired([r for r in rr if r['cores']==n],baseline) for n in sorted({r['cores'] for r in rr})}
    result['validation']=dict(all_initial_candidates_identical=all_prefix,all_four_grains_attempted=all_grain,
                              all_budgets_12=all(r['evaluated_opportunities']==12 for r in rows),
                              all_final_replays_passed=all(r['verification_passed'] for r in rows),
                              failed_artifact_hashes=failed_artifacts)
    assert all_prefix and all_grain and not failed_artifacts and all(r['evaluated_opportunities']==12 and r['verification_passed'] for r in rows)
    return result,paired_rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--primary',type=Path,required=True)
    ap.add_argument('--robustness',type=Path,required=True)
    ap.add_argument('--prior',type=Path,required=True,help='Adopted v18 all_case_results.csv')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    first,pairs=analyze(args.primary);robust,rpairs=analyze(args.robustness)
    priors={(r['case'],int(r['cores'])):int(r['makespan']) for r in csv.DictReader(args.prior.open(encoding='utf-8-sig')) if r['config']=='shared_region'}
    matches=[p['makespan']==priors[p['case'],p['cores']] for p in pairs if p['config']=='shared_region']
    first['baseline_matches_adopted']=dict(matched=sum(matches),total=len(matches))
    write_json(args.output/'summary.json',dict(primary=first,robustness=robust))
    for name,rr in [('paired.csv',pairs),('robustness.csv',rpairs)]:
        with (args.output/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    lines=['# 问题一结构初解同预算验证结果','',
           '本轮范围：十图原型对照。未替换 100 图正式采用基线。协议在正式运行前冻结，详见问题一结构初解同预算实验协议_20260923.md。','',
           '旧开发图：017、045、048、065、077；反例图：002、028、063、067、085。主实验 seed=0、2～5 核、五方案共 200 次求解；稳健性 seed=1/2、五核、基线与组合共 40 次。每次 12 个唯一评价机会（含 1 次固定单核复用），最终原版 A 重放不参与选优。','',
           '## 主实验配对结果','',
           '| 方案 | 胜/平/负（40 配置） | 时间合计下降 | 额外搬运合计下降 | 旧五图时间下降 | 反例时间下降 |',
           '|---|---:|---:|---:|---:|---:|']
    for name in VARIANTS[1:]:
        v=first['variants'][name];a=v['all']
        lines.append(f"| {name} | {a['wins']}/{a['ties']}/{a['losses']} | {a['time_reduction_pct']:.4f}% | {a['added_reduction_pct']:.4f}% | {v['old_five']['time_reduction_pct']:.4f}% | {v['counterexamples']['time_reduction_pct']:.4f}% |")
    lines+=['','正数表示改善，负数表示退步。时间合计与逐例平均加速比采用不同权重。反例大图会主导时间合计。','',
            '## 十图逐例平均加速比五点','',
            '| 核数 | 基线 | 完整分量 | 分量分批 | 深度窗口 | 组合 |','|---|---:|---:|---:|---:|---:|',
            '| 1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |']
    for n in range(2,6):
        lines.append('| '+str(n)+' | '+' | '.join(f"{first['variants'][name]['by_core'][n]['candidate_mean_speedup']:.6f}" for name in VARIANTS)+' |')
    lines+=['','平均加速比为 (1/N)Σ[T_single(case)/T_multi(case,k)]；仅这十图，不是 100 图更新成绩。','',
            '## 多种子稳健性','']
    a=robust['variants']['seed_combined']['all']
    lines.append(f"seed=1、2 的五核 20 个配对：组合 {a['wins']} 胜/{a['ties']} 平/{a['losses']} 负；执行时间合计下降 {a['time_reduction_pct']:.4f}%，额外搬运合计下降 {a['added_reduction_pct']:.4f}%。完整逐例值见 robustness.csv。")
    lines+=['','## 实现与预算证据','',
            '- 新种子在原 single_task、greedy、multilevel 之后进入初始候选；最多四个新评价机会，保护四种基础粒度尝试和至少一次后续搜索。固定原图构造，不靠不断变化的局部观测给种子排序。',
            '- 分量分核同时保留 LPT、Pipe 均衡、轮转；分批目标为 256 个计算操作且不切开分量；深度窗口 8/16/4 只用于占主导的大分量。关闭结构门槛时，该族可能不生成任何新候选，额度留给旧搜索。',
            '- 原三个初解的方案哈希及状态在全部对照中一致。四个基础粒度均尝试，所有求解使用恰好 12 个唯一评价机会；子图标签规范化去重不会挤占新额度。',
            '- 后续官方观测会改变局部成本和搜索父解，因此保留基础粒度尝试不意味着冻结后续全部候选。组合退步点必须按机会成本和路径改变分析。',
            f"- 基线重新运行与既有 v18 成绩相同：{sum(matches)}/{len(matches)}；所有 240 份最终方案均通过原版 A 重放，包含完整时间线和搬运统计。主实验与稳健性计完整候选模拟 {first['score_calls']+robust['score_calls']} 次、固定单核复用 {first['reference_hits']+robust['reference_hits']} 次、最终原版 A 核验 {first['validation_calls']+robust['validation_calls']} 次（单元测试另计）。",
            f"- 主实验墙钟 {first['wall_seconds']:.2f} 秒，稳健性 {robust['wall_seconds']:.2f} 秒；均为并发运行。solve_seconds 包含求解器调用全程，不含固定基准载入和最终核验。候选模拟采用既有等价 counter 后端；这是收费的完整评分，不是免费代理。",'',
            '## 求解耗时（并发观测）','',
            '| 方案 | 中位秒 | 最大秒 | 超过 600 秒的配置 |','|---|---:|---:|---:|']
    for name in VARIANTS:
        a=first['variants'][name]['all'];lines.append(f"| {name} | {a['median_solve_seconds']:.2f} | {a['max_solve_seconds']:.2f} | {a['over_600']} |")
    lines+=['','## 组合退步点','']
    rr=[r for r in first['regressions'] if r['config']=='seed_combined']
    if not rr:lines.append('主实验未观察到组合退步；该结论只覆盖本轮十图。')
    else:
        for r in rr:lines.append(f"- {r['case']} / {r['cores']} 核：{r['baseline_makespan']} → {r['makespan']} cycles，时间变化 {-r['time_reduction_pct']:+.4f}%；最终 {r['best_candidate']}。原赢家 {r['baseline_best_candidate']}，其精确方案是否再次评估：{r['baseline_winner_evaluated']}，同标签的新候选时间：{r['same_label_candidate_times']}。")
    lines+=['','## 下一步与来源','',
            '先按配对结果选择值得保留的候选族，再固定候选顺序和预算跑全部 100 图；不能把本轮十图或事后择优结果写成全量成绩。反例结果应一并保留。若最终组合优于基线但某单项明显更稳，优先验证较小的候选组合，避免不必要的预算挤占。',
            '结构生成核心改编自用户提供的 npu_schedule_project/src/solver.py（归档 SHA256 48aaca6e46f9ddc2d0e846e303dfe841bec2f8f0ab12afeb0898b7b7805d9e8f）。新增工作是与现有求解器的预算保护、规范化去重、消融和核验集成。没有移植对方的 A/B 证书引擎，也没有将借用方法声称为原创。',
            '这是一轮原型增强。正式阶段门禁、人工复核和论文采用状态均未推进。']
    report=ROOT/'审查/问题一结构初解同预算验证_20260923.md'
    report.write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(primary={n:r['all'] for n,r in first['variants'].items()},robustness=robust['variants']['seed_combined']['all']),ensure_ascii=False))


if __name__=='__main__':main()
