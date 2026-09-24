"""Frozen paired global-cost calibration and opportunity trace audit."""
import argparse, csv, json
from pathlib import Path
from statistics import mean
from q1_io import ROOT, verify, sha, write_json
from q1_opportunity_report import check_run, folder, key, load, comparison


def trajectory(st):
    return {r['plan_sha256']:r['evaluation_id'] for r in st['proposal_ledger'] if r['status']=='evaluated'}


def audits(root, rows, baseline_root, baseline):
    control={key(r):r for r in rows if r['config']=='routes_unguarded'}
    trials=[r for r in rows if r['config']=='routes_event_guarded']
    gates=[];opportunities=[]
    for r in trials:
        c=control[key(r)];st=load(folder(root,r)/'search.json');ct=load(folder(root,c)/'search.json')
        bp=folder(baseline_root,baseline[key(r)])
        for name,h in baseline[key(r)]['artifacts'].items():assert sha((bp/name).read_bytes())==h
        bt=load(bp/'search.json');base_hash=trajectory(bt)
        current_hash=trajectory(ct)
        missing=[];best=bt['evaluations'][0]['makespan']
        by_index={v:k for k,v in base_hash.items()}
        for i,x in enumerate(bt['evaluations'][1:],1):
            gain=max(0,best-x['makespan'])
            if gain and by_index[i] not in current_hash:
                missing.append(dict(index=i,candidate=x['candidate'],makespan=x['makespan'],prefix_gain=gain,plan_sha256=by_index[i]))
            best=min(best,x['makespan'])
        for rec in ct['structural_seed_stats'].get('ledger',[]):
            if 'replaced_plan_sha256' not in rec:continue
            matched_proposals=[x for x in bt['proposal_ledger'] if x['plan_sha256']==rec['replaced_plan_sha256'] and x['candidate']==rec['replaces_candidate']]
            matched=matched_proposals[0] if matched_proposals else None
            idx=base_hash.get(rec['replaced_plan_sha256'])
            actual=bt['evaluations'][idx] if idx is not None else None
            prefix=min((x['makespan'] for x in bt['evaluations'][:idx]),default=bt['evaluations'][0]['makespan']) if idx is not None else None
            opportunities.append(dict(case=r['case'],cores=r['cores'],new_route=bool(ct['structural_seed_stats'].get('route')),structural_status=rec['status'],consumed_score=rec['status']=='evaluated' and not rec.get('cache_hit',False),replacement=rec['candidate'],replaced=rec['replaces_candidate'],replacement_at=rec['replacement_at_evaluation'],already_scored_id=rec['replaced_exact_evaluation_id'],baseline_match_index=idx,baseline_proposal_status=matched['status'] if matched else 'unmatched',baseline_rejection_reason=matched.get('reason') if matched else None,direct_gain_in_baseline_prefix=(0 if matched and matched['status'] in ['infeasible','duplicate'] else (max(0,prefix-actual['makespan']) if actual else None)),baseline_missing_improvers=missing,baseline_final=baseline[key(r)]['makespan'],unguarded_final=c['makespan'],guarded_final=r['makespan'],causal_scope='same-plan direct score where matched; missing later improvements are trajectory differences, not isolated causal attribution'))
        for rec in st['structural_seed_stats'].get('ledger',[]):
            if 'event_comparison' not in rec:continue
            d=rec['event_comparison'];assert d['allowed']==(d['candidate_event']<d['incumbent_event'])
            assert d['full_score_calls']==0 and d['local_preparation_calls']==2 and d['preparation']['global_evaluations']==0
            matches=[x for x in ct['structural_seed_stats']['ledger'] if x['candidate']==rec['candidate'] and x['status']=='evaluated']
            assert len(matches)==1
            other=matches[0]
            assert other['incumbent_plan_sha256']==rec['incumbent_plan_sha256']
            assert other['incumbent_makespan']==rec['incumbent_makespan']
            assert ct['structural_seed_stats']['ranked']==st['structural_seed_stats']['ranked']
            official=ct['evaluations'][other['evaluation_id']]['makespan'];inc=rec['incumbent_makespan']
            gates.append(dict(case=r['case'],cores=r['cores'],candidate=rec['candidate'],official=official,incumbent_official=inc,real_improvement=official<inc,local_allows=d['candidate_local']<d['incumbent_local'],event_allows=d['allowed'],candidate_local=d['candidate_local'],incumbent_local=d['incumbent_local'],candidate_event=d['candidate_event'],incumbent_event=d['incumbent_event'],preparation_seconds=d['seconds'],local_calls=d['local_preparation_calls'],final_guarded=r['makespan'],final_unguarded=c['makespan']))
    return trials,control,gates,opportunities


def score_gates(rows):
    if not rows:return {'n':0}
    result={'n':len(rows),'preparation_seconds':sum(x['preparation_seconds'] for x in rows),'local_preparation_calls':sum(x['local_calls'] for x in rows)}
    for method in ['local','event']:
        result[method]=dict(correct_decisions=sum(x[method+'_allows']==x['real_improvement'] for x in rows),false_rejects=sum(not x[method+'_allows'] and x['real_improvement'] for x in rows),false_accepts=sum(x[method+'_allows'] and not x['real_improvement'] for x in rows),candidate_mape_pct=mean(abs(x['candidate_'+method]/x['official']-1)*100 for x in rows),incumbent_mape_pct=mean(abs(x['incumbent_'+method]/x['incumbent_official']-1)*100 for x in rows))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    manifest=verify();old=ROOT/'图表/runs/20260924-A-q1-ranking-full100';base_summary=load(old/'summary.json');baseline={key(r):r for r in base_summary['runs']}
    assert base_summary['source_zip_sha256']==manifest['source_sha256']
    assert base_summary['config_sha256']==manifest['files']['data/config.txt']
    decision=load(a.run/'frozen_extension_decision.json')
    out={'scope':'8 development graphs; conditional 16 extension graphs, not full100','default_changed':False,'extension_started':decision['proceed'],'checks':decision['checks']}
    exports=[];allrows=[];allaudits=[];allopp=[]
    for stage in ['development']+(['extension'] if decision['proceed'] else []):
        root=a.run/'runs'/stage;s,_=check_run(root,manifest);assert s['code_sha256']==decision['code_sha256']
        t,c,g,o=audits(root,s['runs'],old,baseline)
        assert len(t)==(32 if stage=='development' else 64)
        out[stage]={'paired':comparison(t,c),'vs_baseline':comparison(t,baseline),'prediction_audit':score_gates(g),'average_speedup_by_core':{k:{'baseline':mean(x['single_makespan']/baseline[key(x)]['makespan'] for x in t if x['cores']==k),'unguarded':mean(x['single_makespan']/c[key(x)]['makespan'] for x in t if x['cores']==k),'event_guarded':mean(x['speedup'] for x in t if x['cores']==k)} for k in range(2,6)}}
        for r in t:exports.append(dict(stage=stage,case=r['case'],cores=r['cores'],baseline=baseline[key(r)]['makespan'],unguarded=c[key(r)]['makespan'],event_guarded=r['makespan'],unguarded_bytes=c[key(r)]['added_copy_bytes'],event_guarded_bytes=r['added_copy_bytes'],unguarded_solve_seconds=c[key(r)]['solve_seconds'],event_solve_seconds=r['solve_seconds']))
        allrows+=s['runs'];allaudits += [dict(stage=stage,**x) for x in g];allopp += [dict(stage=stage,**x) for x in o]
    from collections import Counter
    out['opportunity_status_counts']={'all_attempted':dict(Counter(x['baseline_proposal_status'] for x in allopp)),'consumed_scores_only':dict(Counter(x['baseline_proposal_status'] for x in allopp if x['consumed_score'])),'new_route_consumed_only':dict(Counter(x['baseline_proposal_status'] for x in allopp if x['new_route'] and x['consumed_score']))}
    out['budget']={'runs':len(allrows),'global_search_calls':sum(r['full_score_calls'] for r in allrows),'fixed_reference_hits':sum(r['fixed_reference_hits'] for r in allrows),'original_final_replays':sum(r['verification_calls'] for r in allrows),'strict_original_verification_reuse':sum(r['verification_reused'] for r in allrows),'event_extra_local_calls':sum(x['local_calls'] for x in allaudits)}
    out['runtime']={'search_seconds_sum_by_variant':{name:sum(r['solve_seconds'] for r in allrows if r['config']==name) for name in ['routes_unguarded','routes_event_guarded']},'max_search_seconds':max(r['solve_seconds'] for r in allrows),'search_over_600':[(r['case'],r['cores'],r['config'],r['solve_seconds']) for r in allrows if r['solve_seconds']>600],'scope':'16 workers; search excludes fixed-single cold generation and final original replay; comparison records per-run values, not speed guarantee'}
    write_json(a.output/'summary.json',out);write_json(a.output/'prediction_audit.json',allaudits);write_json(a.output/'opportunity_audit.json',allopp)
    with (a.output/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(exports[0]));w.writeheader();w.writerows(exports)
    lines=['# 全局成本机制校准与预算机会审计','','本报告旧基线指冻结的component_local_rank全量实验，不表示main默认已更新。固定三轮Pipe/依赖/DDR代理；不拟合逐例系数、不改变候选池和候选排序。准入只比较同口径候选与当前解。代理不是完整官方全局仿真；核内准备和代理耗时另列。','',f"扩展条件通过：{decision['proceed']}。",'']
    for stage in ['development','extension']:
        if stage not in out:continue
        x=out[stage];p=x['paired'];g=x['prediction_audit']
        lines += [f'## {stage}', '',f"同预算相对未筛选：{p['wins']}胜/{p['ties']}平/{p['losses']}负，合计时间下降{p['time_reduction_pct']:.6f}%，额外搬运下降{p['added_reduction_pct']:.6f}%。",f"固定当前解与同候选池预测诊断：{g}。",'', '|核心|旧基线平均加速比|未筛选|事件筛选|','|---|---:|---:|---:|','|1|1|1|1|']
        for k,v in x['average_speedup_by_core'].items():lines.append(f"|{k}|{v['baseline']:.6f}|{v['unguarded']:.6f}|{v['event_guarded']:.6f}|")
        lines+=['','退步配置（完整保留）：']
        losses=[r for r in exports if r['stage']==stage and r['event_guarded']>r['unguarded']]
        lines += [f"- {r['case']} / {r['cores']}核：{r['unguarded']}→{r['event_guarded']}。" for r in losses] or ['- 无。']
    lines+=['','## 基础搜索机会成本','']
    for x in allopp:
        if x['stage']=='development' and x['case']=='case_028' and x['cores']==4:lines.append(json.dumps(x,ensure_ascii=False))
    lines+=['',f"真实消耗评分的替代分类（未评分的提议单独保留）：{out['opportunity_status_counts']}。",'opportunity_audit.json逐项记录被替代方案的hash匹配及原基线中缺席的有效改进。直接改善按相同方案原基线前缀衡量；后续轨迹差异不能被简单加总为独立因果收益。', '',f"预算：{out['budget']}。",f"耗时：{out['runtime']}。",'','仅seed0；8图开发与16图扩展分开汇报。只在开发门槛通过时扩展；不据本轮自动替换main、默认或全量100图成绩。候选预测改善不等于最终搜索收益，所有筛选误拒/误放及最终退步必须保留。']
    (a.output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode());print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':main()
