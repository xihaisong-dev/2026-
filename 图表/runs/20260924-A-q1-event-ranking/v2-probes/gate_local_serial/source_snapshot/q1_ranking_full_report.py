"""Verify fixed ranking experiments, full100 scores and structural loss contributions."""
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean
from q1_io import PROCESSED, official, verify, sha, write_json
from q1_seed_report import paired
from q1_rank_metrics import metrics
from q1_structural_seeds import GraphModel


def load(p):return json.loads(p.read_text(encoding='utf8'))
def key(r):return r['case'],r['cores'],r['seed']
def folder(root,r):return root/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}"
def signature(s):return [(x['candidate'],x['makespan'],x['added_copy_bytes']) for x in s['evaluations']]
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvwrite(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def verify_run(root):
    s=load(root/'summary.json');assert s['completed'] and not s['failures'] and len(s['runs'])==s['expected_runs']
    assert len({key(r)+(r['config'],) for r in s['runs']})==len(s['runs'])
    for name,h in s['code_sha256'].items():assert sha((root/'source_snapshot'/name).read_bytes())==h
    for r in s['runs']:
        p=folder(root,r)
        for name,h in r['artifacts'].items():assert sha((p/name).read_bytes())==h
        assert all(load(p/'verification.json').values()) and r['verification_passed']
        stats=load(p/'search.json');assert r['evaluated_opportunities']==len(stats['evaluations'])==12
        assert r['full_score_calls']==11 and r['fixed_reference_hits']==1
        assert stats['protected_grain_attempts']==[.5,1.,2.,.25]
        assert abs(r['speedup']-r['single_makespan']/r['makespan'])<1e-12
        assert (r['makespan'],r['added_copy_bytes'])==min((e['makespan'],e['added_copy_bytes']) for e in stats['evaluations'])
        prep=stats['structural_seed_stats'].get('local_preparation',{})
        assert prep.get('global_evaluations',0)==0 and prep.get('calls',0)<=3
    return s

def paired_validation(root,old):
    s=verify_run(root);rows=s['runs'];base={key(r):r for r in rows if r['config']=='component_followup'}
    prior={key(r):r for r in load(old/'summary.json')['runs'] if r['config']=='component_followup'}
    for k,r in base.items():
        a=folder(root,r);b=folder(old,prior[k]);assert load(a/'plan.json')==load(b/'plan.json')
        assert signature(load(a/'search.json'))==signature(load(b/'search.json'))
    rr=[r for r in rows if r['config']=='component_local_rank']
    result=paired(rr,base);result['by_core']={n:paired([r for r in rr if r['cores']==n],base) for n in sorted({r['cores'] for r in rr})}
    result['regressions']=[dict(case=r['case'],cores=r['cores'],seed=r['seed'],before=base[key(r)]['makespan'],after=r['makespan']) for r in rr if r['makespan']>base[key(r)]['makespan']]
    result['baseline_trajectory_matches']=len(base)
    result['local_preparation_seconds']=sum(load(folder(root,r)/'search.json')['structural_seed_stats'].get('local_preparation',{}).get('seconds',0) for r in rr)
    return result,s

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['audit','validation','robustness','prior-validation','prior-robustness','full','execution','baseline','output']:ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False);manifest=verify()
    audit=load(args.audit/'summary.json');assert audit['completed']
    assert sha((args.audit/'frozen_predictions.json').read_bytes())==audit['frozen_predictions_sha256']
    for p in audit['pools']:
        root=args.audit/'pools'/f"{p['case']}_{p['cores']}cores"
        for r in p['rows']:
            assert sha((root/f"{r['label']}_plan.json").read_bytes())==r['plan_sha256']
            assert sha((root/f"{r['label']}_evaluation.json.gz").read_bytes())==r['evaluation_sha256']
    # Report tie-aware correlation of raw scores; selection regrets retain the
    # frozen generation-order tie break used by the deployed ranker.
    raw_aggregate=json.loads(json.dumps(audit['aggregate']))
    for field in raw_aggregate:
        correlations=[metrics(p['rows'],field)['spearman'] for p in audit['pools']]
        defined=[x for x in correlations if x is not None]
        raw_aggregate[field]['mean_spearman']=mean(defined) if defined else None
        raw_aggregate[field]['defined_rho']=len(defined)
    v,vs=paired_validation(args.validation,args.prior_validation);rob,rs=paired_validation(args.robustness,args.prior_robustness)
    full=verify_run(args.full);rows=full['runs'];assert len(rows)==400
    selection=load(args.execution/'frozen_selection.json');selected=selection['selected']
    assert {r['config'] for r in rows}=={selected} and full['code_sha256']==selection['code_sha256']==vs['code_sha256']==rs['code_sha256']
    before={key(r):r for r in vs['runs'] if r['config']==selected};replayed=0
    for r in rows:
        if key(r) in before:
            prior=before[key(r)];assert load(folder(args.full,r)/'plan.json')==load(folder(args.validation,prior)/'plan.json')
            assert r['makespan']==prior['makespan'] and r['added_copy_bytes']==prior['added_copy_bytes'];replayed+=1
    assert replayed==56
    base={(r['case'],int(r['cores'])):r for r in csvread(args.baseline) if r['config'] in ['fixed_single','shared_region']}
    ext={(r['case'],int(r['cores'])):r for r in csvread(args.execution/'external_comparison_500.csv')}
    external_meta=load(args.execution/'external_comparison.json')
    for r in external_meta['hash_checks']:assert r['match'] and r['sha256']==manifest['files'][r['path']]
    summary_core={};out=[];structures={};official()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    settings=read_evaluation_config(str(PROCESSED/'data/config.txt'));waits=read_scene_a_config(str(PROCESSED/'data/config.txt'))
    for case in sorted({r['case'] for r in rows}):
        raw=json.loads((PROCESSED/'data'/f'{case}.json').read_text(encoding='utf-8-sig'));m=GraphModel(raw,settings,waits)
        work=[max(m.cost_vector(g).values()) for g in m.components]
        structures[case]=dict(case=case,noncopy_ops=len(m.ids),components=len(m.components),max_depth=max(m.depth.values(),default=0),
            largest_component_node_fraction=max(map(len,m.components),default=0)/max(1,len(m.ids)),largest_component_work_fraction=max(work,default=0)/max(1,sum(work)))
    for r in sorted(rows,key=lambda r:(r['case'],r['cores'])):
        k=(r['case'],r['cores']);b=base[k];e=ext[k];single=int(base[r['case'],1]['makespan']);assert single==r['single_makespan']==int(ext[r['case'],1]['external_makespan'])
        assert int(e['our_makespan'])==int(b['makespan'])
        stats=load(folder(args.full,r)/'search.json');plan=load(folder(args.full,r)/'plan.json')
        rec=dict(case=r['case'],cores=r['cores'],single_makespan=single,baseline_makespan=int(b['makespan']),makespan=r['makespan'],external_makespan=int(e['external_makespan']),
            baseline_speedup=single/int(b['makespan']),speedup=r['speedup'],external_speedup=single/int(e['external_makespan']),
            baseline_added_bytes=int(b['added_copy_bytes']),added_bytes=r['added_copy_bytes'],external_added_bytes=int(e['external_added_bytes']),
            spill_added_bytes=r['spill_added_copy_bytes'],partition_added_bytes=r['partition_added_copy_bytes'],
            mean_speedup_loss_contribution=(single/int(e['external_makespan'])-r['speedup'])/100,
            gate=stats['structural_seed_stats'].get('gate'),tasks=r['final_tasks'],used_cores=sum(bool(x) for x in plan['core_schedules']),
            solve_seconds=r['solve_seconds'],validation_seconds=r['verification_seconds'],local_prepare_seconds=stats['structural_seed_stats'].get('local_preparation',{}).get('seconds',0),
            best_candidate=r['best_candidate'],**{k:x for k,x in structures[r['case']].items() if k!='case'})
        out.append(rec)
    for n in range(2,6):
        rr=[r for r in out if r['cores']==n]
        summary_core[n]=dict(count=100,baseline_mean_speedup=mean(r['baseline_speedup'] for r in rr),mean_speedup=mean(r['speedup'] for r in rr),external_mean_speedup=mean(r['external_speedup'] for r in rr),
            sum_makespan=sum(r['makespan'] for r in rr),baseline_sum_makespan=sum(r['baseline_makespan'] for r in rr),external_sum_makespan=sum(r['external_makespan'] for r in rr),
            added_bytes=sum(r['added_bytes'] for r in rr),baseline_added_bytes=sum(r['baseline_added_bytes'] for r in rr),external_added_bytes=sum(r['external_added_bytes'] for r in rr),
            versus_baseline={label:sum(op(r['makespan'],r['baseline_makespan']) for r in rr) for label,op in [('wins',lambda a,b:a<b),('ties',lambda a,b:a==b),('losses',lambda a,b:a>b)]},
            versus_external={label:sum(op(r['makespan'],r['external_makespan']) for r in rr) for label,op in [('wins',lambda a,b:a<b),('ties',lambda a,b:a==b),('losses',lambda a,b:a>b)]})
    contributions=[]
    for case in structures:
        rr=[r for r in out if r['case']==case]
        contributions.append(dict(structures[case],average_point_loss_contribution=sum(r['mean_speedup_loss_contribution'] for r in rr)/4,
            **{f'core{r["cores"]}_loss_contribution':r['mean_speedup_loss_contribution'] for r in rr},gates=';'.join(sorted({r['gate'] for r in rr}))))
    contributions.sort(key=lambda x:-x['average_point_loss_contribution'])
    by_gate={}
    for gate in sorted({r['gate'] for r in out}):
        rr=[r for r in out if r['gate']==gate];by_gate[gate]=dict(count=len(rr),average_point_loss_contribution=sum(r['mean_speedup_loss_contribution'] for r in rr)/4)
    result=dict(selected=selected,formal_default_changed=False,validation=v,robustness=rob,audit_aggregate=raw_aggregate,selection_order_aggregate=audit['aggregate'],full_by_core=summary_core,
        full100_repeated_validation_matches=replayed,ranking_loss_by_gate=by_gate,top_loss_cases=contributions[:15],top_advantage_cases=contributions[-10:],
        full_score_calls=sum(r['full_score_calls'] for r in rows),full_reference_hits=400,full_validation_calls=400,
        diagnostic_global_calls=audit['pool_global_calls']+audit['trace_global_calls'],validation_score_calls=1672,validation_reference_hits=152,validation_replays=152,
        max_solve_seconds=max(r['solve_seconds'] for r in rows),solve_over_600=sum(r['solve_seconds']>600 for r in rows),
        source_summaries={str(p):sha((p/'summary.json').read_bytes()) for p in [args.audit,args.validation,args.robustness,args.full]},all_checks_passed=True)
    write_json(args.output/'summary.json',result);csvwrite(args.output/'all_case_results.csv',out);csvwrite(args.output/'structure_loss_contributions.csv',contributions)
    lines=['# 问题一排序诊断、同预算对照与全量结果','',f'冻结配置：{selected}。所有100图、2～5核、seed0；单核为既有官方固定基准。正式默认尚未替换。','',
        '## 预算台账与固定池排序','',
        '12组原搜索重建完全一致，12次local_reschedule仅改变核心编号，另外3次区域修复也是核心置换；这15次的本次官方时间相同。其他129次属于不同结构。不同结构但同分不作为重复；核心置换未被直接用作跨方案结果缓存。',
        '18个最多三候选固定池，所有预测先冻结后取官方结果；原排序和任务代理不足以可靠反映核内启发式调度差异。局部排序使用官方局部准备，不运行完整共享DDR模拟；耗时单列。',
        '| 排序 | 有定义池的平均Spearman | 平均相对选择遗憾 | 前两名覆盖率 |','|---|---:|---:|---:|']
    for name,a in raw_aggregate.items():lines.append(f"| {name} | {a['mean_spearman']:.6f} | {100*a['mean_relative_regret']:.6f}% | {100*a['top2_coverage']:.2f}% |")
    lines+=['','相关系数对原始预测分数的并列取平均秩；选中遗憾及覆盖率则按冻结的候选生成顺序破平局。小池相关性不代表全图全邻域排序可靠。独立诊断新增50次固定池官方评分、132次轨迹完整评分及12次单核引用，与正式求解预算分开。','', '## 14图同预算验证','',
        f"相对followup：{v['wins']}/{v['ties']}/{v['losses']}，总时间下降{v['time_reduction_pct']:.6f}%，搬运下降{v['added_reduction_pct']:.6f}%。双种子：{rob['wins']}/{rob['ties']}/{rob['losses']}，时间下降{rob['time_reduction_pct']:.6f}%。",
        '全部152份方案原版复核通过；每次12机会，其中1次固定单核引用。两组对照源代码一致，76份旧方案轨迹匹配上一轮。规则按预定开发组改善和大图不退步条件冻结，再启动全量；不根据100图结果修改。','',
        '## 100图平均加速比','', '| 核数 | 原基线 | 冻结新方案 | 参考工程 |','|---|---:|---:|---:|','| 1 | 1.000000 | 1.000000 | 1.000000 |']
    for n,a in summary_core.items():lines.append(f"| {n} | {a['baseline_mean_speedup']:.6f} | {a['mean_speedup']:.6f} | {a['external_mean_speedup']:.6f} |")
    lines+=['','统一平均为各用例T1/Tk的算术平均，不是总时间之比。原基线与参考工程复用已核验历史结果；参考工程搜索预算不同，不能据此作同耗时算法效率因果比较。全量新旧对比同时包含先前完整分量初解、条件预算和本轮排序，不能把全部收益归因于本轮排序；排序单因素证据仅来自上述14图同预算对照。','',
        '| 核数 | 原基线总时间 | 新方案总时间 | 参考总时间 | 新方案对参考胜/平/负 |','|---|---:|---:|---:|---:|']
    for n,a in summary_core.items():
        w=a['versus_external'];lines.append(f"| {n} | {a['baseline_sum_makespan']} | {a['sum_makespan']} | {a['external_sum_makespan']} | {w['wins']}/{w['ties']}/{w['losses']} |")
    lines+=['','## 平均加速比损失最大的结构','', '每核每图贡献=(参考加速比−新方案加速比)/100；下表取四个多核点等权平均贡献，仅用于定位，不另造赛题评分。正数表示参考更好，负数表示我们更好；结构关联不代表因果。','',
        '| case | 非COPY算子 | 分量数 | 最大分量工作占比 | 四点平均差距贡献 | 路由 |','|---|---:|---:|---:|---:|---|']
    for r in contributions[:15]:lines.append(f"| {r['case']} | {r['noncopy_ops']} | {r['components']} | {r['largest_component_work_fraction']:.4f} | {r['average_point_loss_contribution']:.6f} | {r['gates']} |")
    lines+=['','## 退步与开销','']
    for r in v['regressions']+rob['regressions']:lines.append(f"- 验证 {r['case']} / {r['cores']}核 / seed{r['seed']}：{r['before']} → {r['after']}。")
    bad=sorted([r for r in out if r['makespan']>r['baseline_makespan']],key=lambda r:r['makespan']/r['baseline_makespan'],reverse=True)
    lines.append(f'全量相对原基线有{len(bad)}组时间退步，逐例CSV全部保留；最大相对退步前十：')
    for r in bad[:10]:lines.append(f"- {r['case']} / {r['cores']}核：{r['baseline_makespan']} → {r['makespan']}（{100*(r['makespan']/r['baseline_makespan']-1):.4f}%）。")
    lines += ['',f"全量400份原版A最终复核全部通过；4400次完整评分、400次固定单核引用、400次原版最终复核。56份与小矩阵重复的方案结果完全一致。最长搜索{result['max_solve_seconds']:.3f}秒，超过600秒{result['solve_over_600']}份；不含固定单核冷计算和最终复核，不是任意图硬时限保证。",'局部准备不是免费计算；逐例local_prepare_seconds、solve_seconds、validation_seconds均保留。所有局部准备global_evaluations=0；全局评分没有隐藏在排序器里。','正式阶段门禁、人工接收和main采用均未推进。']
    lines += ['', '## 下一轮优先级', '',
        '1. 核查保守内存路由：case_058、039、072 是前三项正差距贡献，均被 union footprint 规则跳过。张量大小并集不是同时活跃峰值，不能据此断言必然溢出。先对固定少量分量布局做局部官方准备，区分实际溢出与假阳性，再验证有界分量分批；不要直接删除全部保护。',
        '2. 处理主导分量：dominant_component 路由覆盖71组，是净差距贡献最大的路由。优先 case_009、100、040，保留小分量完整，仅在大分量内做有界切分；与核心布局联合评分。路由统计是关联，需单独消融证明因果。',
        '3. 核心置换重复的15次官方评分值得单独审计，但本轮没有将其变为全局缓存。确认评估器对编号及并列事件顺序的语义后，再验证能否释放机会给结构不同候选。',
        '4. 保护 case_028、067 等大图优势；4组搜索仍超过600秒，应检查局部准备复用和搜索开销。服务器16并发下的墙钟不能直接作为单用例独占机器性能。',
        '上述是下一轮待验证假设；本轮已冻结，不以全量观察回改方案再重报同一成绩。', '',
        '| 核数 | 相对原基线总时间下降 | 额外搬运下降 | 相对参考总时间下降 |', '|---|---:|---:|---:|']
    for n,a in summary_core.items():
        lines.append(f"| {n} | {100*(1-a['sum_makespan']/a['baseline_sum_makespan']):.4f}% | {100*(1-a['added_bytes']/a['baseline_added_bytes']):.4f}% | {100*(1-a['sum_makespan']/a['external_sum_makespan']):.4f}% |")
    (args.output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode())
    print(json.dumps({'selected':selected,'full_by_core':summary_core,'top_losses':contributions[:5]},ensure_ascii=False))

if __name__=='__main__':main()
