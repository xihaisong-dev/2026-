"""Audit screening decisions and paired extension scores without oracle selection."""
import argparse, csv, gzip, json
from pathlib import Path
from statistics import mean
from q1_io import ROOT, verify, sha, write_json


def load(p):return json.loads(p.read_text(encoding='utf8'))
def key(r):return r['case'],r['cores']
def folder(root,r):return root/f"{r['case']}_{r['cores']}cores_seed{r['seed']}_{r['config']}"


def local_source(remote):
    parts=remote.replace('\\','/').split('/')
    if '20260924-A-q1-ranking-full100' in parts:
        return ROOT/'图表/runs/20260924-A-q1-ranking-full100'/parts[-1]
    if 'memory-routing-20260924-r01' in parts:
        return ROOT/'图表/runs/20260924-A-q1-memory-routing/validation/runs'/parts[-2]/parts[-1]
    raise ValueError('Unrecognized verification source')


def check_run(root,manifest):
    s=load(root/'summary.json');assert s['completed'] and not s['failures'] and len(s['runs'])==s['expected_runs']
    assert len({(r['case'],r['cores'],r['seed'],r['config']) for r in s['runs']})==len(s['runs'])
    assert s['source_zip_sha256']==manifest['source_sha256'] and s['config_sha256']==manifest['files']['data/config.txt']
    for name,h in s['input_sha256'].items():assert h==manifest['files']['data/'+name]
    for name,h in s['code_sha256'].items():assert sha((root/'source_snapshot'/name).read_bytes())==h
    decisions=[]
    for r in s['runs']:
        p=folder(root,r)
        for name,h in r['artifacts'].items():assert sha((p/name).read_bytes())==h
        assert all(load(p/'verification.json').values()) and r['verification_passed']
        st=load(p/'search.json');assert len(st['evaluations'])==12 and st['official_calls']==11 and st['cache_hits']==1
        assert st['protected_grain_attempts']==[.5,1.,2.,.25]
        assert (r['makespan'],r['added_copy_bytes'])==min((x['makespan'],x['added_copy_bytes']) for x in st['evaluations'])
        if r['verification_reused']:
            ref=load(p/'verification_reuse.json');src=local_source(ref['source'])
            assert sha((src.parent/'summary.json').read_bytes())==ref['summary_sha256']
            for name,h in ref['artifacts'].items():assert sha((src/name).read_bytes())==h
            assert (p/'plan.json').read_bytes()==(src/'plan.json').read_bytes()
            assert json.loads(gzip.decompress((p/'evaluation.json.gz').read_bytes()))==json.loads(gzip.decompress((src/'evaluation.json.gz').read_bytes()))
            assert all(load(src/'verification.json').values()) and load(src/'row.json')['verification_calls']==1
        for entry in st['structural_seed_stats'].get('ledger',[]):
            if 'opportunity_comparison' not in entry:continue
            d=entry['opportunity_comparison']
            assert d['allowed']==(d['candidate_local']<d['incumbent_local'])
            assert d['full_score_calls']==d['local_preparation_calls']==0
            decisions.append(dict(case=r['case'],cores=r['cores'],config=r['config'],status=entry['status'],**d))
    return s,decisions


def comparison(rows,base):
    return dict(count=len(rows),wins=sum(r['makespan']<base[key(r)]['makespan'] for r in rows),
                ties=sum(r['makespan']==base[key(r)]['makespan'] for r in rows),losses=sum(r['makespan']>base[key(r)]['makespan'] for r in rows),
                time_reduction_pct=100*(1-sum(r['makespan'] for r in rows)/sum(base[key(r)]['makespan'] for r in rows)),
                added_reduction_pct=100*(1-sum(r['added_copy_bytes'] for r in rows)/sum(base[key(r)]['added_copy_bytes'] for r in rows)))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);manifest=verify()
    old=ROOT/'图表/runs/20260924-A-q1-ranking-full100';baseline={key(r):r for r in load(old/'summary.json')['runs']}
    dev,decisions=check_run(a.run/'runs/development',manifest)
    decision=load(a.run/'frozen_extension_decision.json');assert dev['code_sha256']==decision['code_sha256']
    result=dict(default_changed=False,scope='eight development graphs completed; sixteen-graph extension conditional, not full100',development=comparison(dev['runs'],baseline),extension_decision=decision)
    paired=[];controls={};audit=[]
    for r in dev['runs']:
        st=load(folder(a.run/'runs/development',r)/'search.json')
        route=st['structural_seed_stats'].get('route','hybrid')
        prior=ROOT/'图表/runs/20260924-A-q1-memory-routing/validation/runs'/('component_'+route)
        c=next(x for x in load(prior/'summary.json')['runs'] if key(x)==key(r))
        cp=folder(prior,c);ct=load(cp/'search.json');controls[key(r)]=c
        for name,h in c['artifacts'].items():assert sha((cp/name).read_bytes())==h
        for rec in st['structural_seed_stats'].get('ledger',[]):
            if 'opportunity_comparison' not in rec:continue
            matching=[x for x in ct['structural_seed_stats'].get('ledger',[]) if x['candidate']==rec['candidate'] and x['status']=='evaluated']
            if not matching:continue
            other=matching[0]
            assert rec['incumbent_makespan']==other['incumbent_makespan']
            assert st['structural_seed_stats']['ranked']==ct['structural_seed_stats']['ranked']
            actual=ct['evaluations'][other['evaluation_id']]['makespan']
            audit.append(dict(case=r['case'],cores=r['cores'],allowed=rec['opportunity_comparison']['allowed'],candidate_local=rec['opportunity_comparison']['candidate_local'],incumbent_local=rec['opportunity_comparison']['incumbent_local'],incumbent=rec['incumbent_makespan'],candidate_official=actual,candidate_really_improves=actual<rec['incumbent_makespan'],final_guarded=r['makespan'],final_unguarded=c['makespan']))
    result['development_paired']=comparison(dev['runs'],controls)
    result['development_gate_audit']=dict(matched=len(audit),screened_good=sum(not x['allowed'] and x['candidate_really_improves'] for x in audit),screened_nonimproving=sum(not x['allowed'] and not x['candidate_really_improves'] for x in audit),allowed_nonimproving=sum(x['allowed'] and not x['candidate_really_improves'] for x in audit))
    write_json(a.output/'development_gate_audit.json',audit)
    exports=[];allruns=list(dev['runs'])
    for r in dev['runs']:
        b=baseline[key(r)];exports.append(dict(stage='development',case=r['case'],cores=r['cores'],before=b['makespan'],after=r['makespan'],before_bytes=b['added_copy_bytes'],after_bytes=r['added_copy_bytes']))
    if decision['proceed']:
        ext,more=check_run(a.run/'runs/extension',manifest);assert ext['code_sha256']==dev['code_sha256']
        decisions+=more;allruns+=ext['runs']
        control={key(r):r for r in ext['runs'] if r['config']=='routes_unguarded'}
        trial=[r for r in ext['runs'] if r['config']=='routes_guarded']
        assert len(control)==len(trial)==64
        gate_audit=[]
        for r in trial:
            st=load(folder(a.run/'runs/extension',r)/'search.json')
            ct=load(folder(a.run/'runs/extension',control[key(r)])/'search.json')
            for rec in st['structural_seed_stats'].get('ledger',[]):
                if 'opportunity_comparison' not in rec:continue
                matching=[x for x in ct['structural_seed_stats'].get('ledger',[]) if x['candidate']==rec['candidate'] and x['status']=='evaluated']
                if not matching:continue
                other=matching[0]
                assert other['incumbent_makespan']==rec['incumbent_makespan']
                assert ct['structural_seed_stats']['ranked']==st['structural_seed_stats']['ranked']
                actual=ct['evaluations'][other['evaluation_id']]['makespan']
                gate_audit.append(dict(case=r['case'],cores=r['cores'],allowed=rec['opportunity_comparison']['allowed'],incumbent=rec['incumbent_makespan'],candidate_official=actual,candidate_really_improves=actual<rec['incumbent_makespan'],final_guarded=r['makespan'],final_unguarded=control[key(r)]['makespan']))
        write_json(a.output/'paired_gate_audit.json',gate_audit)
        result['gate_audit']=dict(matched=len(gate_audit),screened_good=sum(not r['allowed'] and r['candidate_really_improves'] for r in gate_audit),screened_nonimproving=sum(not r['allowed'] and not r['candidate_really_improves'] for r in gate_audit),allowed_nonimproving=sum(r['allowed'] and not r['candidate_really_improves'] for r in gate_audit))
        result['extension_paired']=comparison(trial,control);result['extension_vs_frozen_baseline']=comparison(trial,baseline)
        result['extension_by_core']={c:dict(control=mean(r['single_makespan']/control[key(r)]['makespan'] for r in trial if r['cores']==c),guarded=mean(r['speedup'] for r in trial if r['cores']==c),baseline=mean(r['single_makespan']/baseline[key(r)]['makespan'] for r in trial if r['cores']==c)) for c in range(2,6)}
        for r in trial:
            b=control[key(r)];exports.append(dict(stage='extension_paired',case=r['case'],cores=r['cores'],before=b['makespan'],after=r['makespan'],before_bytes=b['added_copy_bytes'],after_bytes=r['added_copy_bytes']))
    result['budget']=dict(runs=len(allruns),global_search_calls=sum(r['full_score_calls'] for r in allruns),reference_hits=len(allruns),original_final_replays=sum(r['verification_calls'] for r in allruns),verified_final_reuses=sum(r['verification_reused'] for r in allruns))
    result['screening']=dict(compared=len(decisions),skipped=sum(not r['allowed'] for r in decisions),allowed=sum(r['allowed'] for r in decisions))
    recovered=next(r for r in dev['runs'] if key(r)==('case_028',4));result['case028_core4']=dict(makespan=recovered['makespan'],baseline=baseline[key(recovered)]['makespan'],plan_matches=(folder(a.run/'runs/development',recovered)/'plan.json').read_bytes()==(folder(old,baseline[key(recovered)])/'plan.json').read_bytes())
    write_json(a.output/'summary.json',result);write_json(a.output/'screening_decisions.json',decisions)
    with (a.output/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(exports[0]));w.writeheader();w.writerows(exports)
    lines=['# 候选机会成本：同口径局部筛选及扩展验证','','新增候选仅当局部回放预测严格优于当前最好方案才占用评分机会。当前方案的官方核内时间直接复用；没有额外完整评分，候选原有局部准备仍计耗时。筛选不是全局最优证明。','',f"case_028四核：{result['case028_core4']}。",'',f"开发阶段扩展条件：{decision['proceed']}。"]
    p=result['development_paired']
    lines += ['',f"开发集对上轮未筛选路由（同种子、同候选池、同12次机会）：{p['wins']}胜/{p['ties']}平/{p['losses']}负，合计时间下降{p['time_reduction_pct']:.6f}%，额外搬运下降{p['added_reduction_pct']:.6f}%。",f"配对筛选诊断：{result['development_gate_audit']}。旧轮未启用等价收缩加速，本轮启用；不据此比较求解墙钟耗时。"]
    for x in audit:
        if not x['allowed'] or (x['case']=='case_028' and x['cores']==4):
            lines.append(f"- {x['case']} / {x['cores']}核：allowed={x['allowed']}，局部预测 {x['incumbent_local']}→{x['candidate_local']}，官方候选 {x['incumbent']}→{x['candidate_official']}；最终未筛选 {x['final_unguarded']}→筛选 {x['final_guarded']}。")
    if not decision['proceed']:
        lines += ['','扩展条件未通过，16图128次运行未启动。新筛选不纳入默认。其失败说明同口径的独立局部时长回放仍不足以判断共享DDR下的全局收益；不能把微小预测收益直接当作值得替代基础搜索的证据。下一轮应在固定候选池上诊断预测残差与DDR重叠，并核对被替代基础候选的实际贡献；冻结新规则后再扩展，不能按本轮结果逐例改阈值。']
    if decision['proceed']:
        p=result['extension_paired'];b=result['extension_vs_frozen_baseline']
        lines += ['',f"16图64组，同预算guarded相对unguarded：{p['wins']}胜/{p['ties']}平/{p['losses']}负，合计执行时间下降{p['time_reduction_pct']:.6f}%，额外搬运下降{p['added_reduction_pct']:.6f}%。",f"guarded相对旧全量基线：{b['wins']}胜/{b['ties']}平/{b['losses']}负，合计时间下降{b['time_reduction_pct']:.6f}%。这是本16图结果，不是新的100图成绩。",'', '| 核数 | 旧基线平均加速比 | 未筛选 | 筛选后 |','|---|---:|---:|---:|','|1|1|1|1|']
        for c,r in result['extension_by_core'].items():lines.append(f"|{c}|{r['baseline']:.6f}|{r['control']:.6f}|{r['guarded']:.6f}|")
    if 'gate_audit' in result:lines += ['', f"同候选池且前置当前解相同的配对筛选诊断：{result['gate_audit']}。screened_good表示候选本身能改善当时解却被拒，allowed_nonimproving表示放行后候选未改善；都不能省略。"]
    lines += ['',f"预算台账：{result['budget']}。复核复用只节约重复验证时间，搜索仍每配置11次完整评分+1次固定单核引用。",f"筛选：{result['screening']}。完整逐例CSV和每条筛选预测保留。",'', '## 退步保留','']
    for r in exports:
        if r['after']>r['before']:lines.append(f"- {r['stage']} {r['case']} / {r['cores']}核：{r['before']}→{r['after']}（增加{100*(r['after']/r['before']-1):.6f}%）。")
    lines+=['','只验证seed0；候选池和筛选都可能存在代理误差。开发样本与扩展样本分开汇报，不事后逐例择优，不据此自动改main或正式默认。批次第一次启动因参数遗漏在计算前失败，修复后另目录冻结；本地CLI冒烟另计11次搜索评分，不混入正式矩阵。']
    (a.output/'report.md').write_bytes(('\n'.join(lines)+'\n').encode());print(json.dumps({k:v for k,v in result.items() if k!='extension_decision'},ensure_ascii=False))


if __name__=='__main__':main()
