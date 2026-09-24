"""Check the diagnostic pilot and record a bounded, non-promoted conclusion."""
import csv,gzip,json,time
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_evaluator import load,key
from q2_physical import PhysicalScorer
from q2_route_diagnosis import OUT as DIAG
from q2_reserve_campaign_v2 import OUT,read


def main():
    dest=OUT/'final_checks.json';assert not dest.exists()
    s=read(OUT/'summary.json');d=read(DIAG/'summary.json');records=read(DIAG/'records.json')
    predicted={(r['case'],r['cores']):r for r in read(DIAG/'conditional_reserve.json')['records']}
    settings,delay,_=load();audits=[];changed=[]
    for i in read(OUT/'contract.json')['cases']:
        raw=read(PROCESSED/f'data/case_{i:03}.json')
        for k in range(2,6):
            folder=OUT/f'cases/case_{i:03}/{k}/reserve';plan=read(folder/f'case_{i:03}_multicore_res.json');r=read(folder/'row.json');search=read(folder/'search.json')
            assert r['makespan']==predicted[i,k]['expected_makespan']
            assert key(plan)==predicted[i,k]['expected_plan_sha256']
            assert r['slots']==12 and r['replay_equal']
            assert all(x['status']=='ok' for x in search['evaluations'])
            with gzip.open(folder/'evaluation.json.gz','rt',encoding='utf-8') as f:actual=json.load(f)
            baseline=OUT/f'cases/case_{i:03}/{k}/routed'
            bplan=read(baseline/f'case_{i:03}_multicore_res.json')
            if plan==bplan:
                with gzip.open(baseline/'evaluation.json.gz','rt',encoding='utf-8') as f:assert actual==json.load(f)
            else:
                t=time.perf_counter();profiles=PhysicalScorer(raw,settings,delay).actual_lifetimes(plan,actual)
                changed.append(dict(case=i,cores=k,prepare_seconds=time.perf_counter()-t,peaks={c:v['peak_bytes'] for c,v in profiles.items()}))
            audits.append(dict(case=i,cores=k,prediction_plan_and_cycles_match=True,plan_sha256=key(plan)))
    for p,h in read(DIAG/'source_manifest.json')['files'].items():assert sha((ROOT/p).read_bytes())==h
    for n,h in read(OUT/'contract.json')['sources'].items():assert sha((ROOT/'程序'/n).read_bytes())==h
    checks=dict(status='PASS_DIAGNOSTIC_PILOT',predictions_checked=audits,changed_actual_residency_checks=changed,
                unchanged_plans_and_complete_results=len(audits)-len(changed),formal_default_changed=False,independent_confirmation=False)
    write_json(dest,checks)
    report=['# 问题二结构准入退步诊断与小样本修补 r06','',
        '结论：先修改候选准入的预算使用方式，暂不修改J。16个退步配置全部在J之前就发生初解损失；15个丢失旧链划分候选，1个丢失旧深度划分候选。不是引导J失效导致本轮主要退步。','',
        '诊断读取r05全部400对配置的800条完整搜索轨迹，新增全局评价为0；每份源文件哈希已记录。313个相同起点的配置，其J候选哈希、周期、搬运和最终成绩均相同。','',
        '## 退步分解','',
        '记基础最优周期为B、J带来的周期减少为G，则新旧最终周期差满足ΔT=(B新−B旧)+(G旧−G新)。这是已观测搜索的精确分解，不是把相互依赖的环节当作独立因果贡献。16个退步配置合计初解差32145 cycles，J收益差−933 cycles，最终差31212 cycles；J整体抵消了一部分损失。16个旧基础解本身都优于新方案最终解。','',
        '| 图/核数 | 旧基础 | 新基础 | 旧J收益 | 新J收益 | 最终退步 | 丢失候选 |','|---|---:|---:|---:|---:|---:|---|']
    for r in records:
        if r['outcome']=='loss':report.append(f"| {r['case']:03}/{r['cores']} | {r['legacy_base']} | {r['routed_base']} | {r['legacy_J_gain']} | {r['routed_J_gain']} | {r['final_gap']} | {r['legacy_base_name']} |")
    report += ['','## 修改选择','',
        '不直接强制保留旧链候选：在393个起点能够与历史轨迹匹配的配置中，这种固定替换会相对r05产生15胜、352平、26负，另7个新起点无法仅凭历史轨迹评价。保留旧深度候选同样不能解决主要问题。','',
        '本轮仅回收重复候选名额：保留r05全部不同的基础计划及其同分优先次序，用原菜单中重复计划占据的名额，依次补回缺失的旧第7/8候选；没有重复名额时不改变菜单。结构阈值仍为最大分量占比大于50%，普通J仍4次，总计12次B机会。不按算例编号或此次胜负设置阈值。','',
        '机会数相同不代表实际评价调用数相同：填补重复候选会增加真实评价，且小容量缓存与候选顺序会影响命中率。下面同时报告实际调用和时间，不能把改善声称为等实际调用数的通信代理收益。','',
        '基于完整起点哈希匹配的事后条件推演为13胜387平，全部起点均能匹配；这是对已有轨迹的组合诊断，不是新跑400配置或独立确认。尚未覆盖的新图不能保证不退步。','',
        '## 实跑回归试验','',
        '测试14个图：001/005/012/022/024/035/048/049/050/064/069/071/086/088，覆盖全部退步图并加入原胜例和平例。两方案各56配置，种子0、8基础+4普通J；输入、配置、源码、迁移种子和规则预先冻结，服务器4进程，交替两方案执行顺序。样本经过诊断选择，不能称独立确认。','',
        f"实际对照：{s['outcomes']}；几何平均相对提升{(s['geomean_ratio']-1)*100:.6f}%；各核平均不退步条件={s['per_core_gate']}。原16个退步配置中，{s['original_16_losses_recovered']}个恢复到旧方案或更好。",'',
        '| 核数 | r05 | 重复名额回收 |','|---|---:|---:|']
    report += [f"| {k} | {s['curves']['routed'][str(k)]:.6f} | {s['curves']['reserve'][str(k)]:.6f} |" for k in range(1,6)]
    a,b=s['totals']['routed'],s['totals']['reserve']
    report += ['',f"14图样本额外搬运变化{(b['bytes']/a['bytes']-1)*100:+.6f}%；搜索墙钟秒数合计{a['solve_seconds']:.3f}→{b['solve_seconds']:.3f}，变化{(b['solve_seconds']/a['solve_seconds']-1)*100:+.6f}%。实际搜索评价{a['official_calls']}→{b['official_calls']}；两组机会各672次，独立最终回放共112次。上述样本均值不能与100图r05均值直接比较，也不能充当全量新成绩。",'',
        f"56份新方案的完整计划哈希与周期均符合条件推演；{len(changed)}份变化方案另按真实全局时间线核验驻留容量，其余{56-len(changed)}份与r05计划及完整结果一致。全部最终回放一致。",'',
        '剩余3个原退步配置为049/2、088/3、088/4：没有可回收的重复名额，本轮明确保持r05行为。若继续处理，应研究真正有代价的候选替换，不能增加预算后称原预算改善。','',
        '## 失败记录与采用边界','',
        '首轮验证把内存中的整数核心键与历史JSON字符串键直接比较，触发断言，未形成完整对照。官方单次重放定位为memory_peak_by_core与step3_by_core的键类型差异，JSON统一表示后所有字段一致。r06-v2只修正历史结果的JSON表示比较，算法和预算未改；失败目录、日志和8份已保存结果保留，不混入正式回归汇总。定位额外调用1次官方B，失败试验中未保存的实际调用数未完整记录，不冒充精确总预算。','',
        '建议把重复名额回收保留为候选优化，暂不修改J或默认r05交付。当前14图为事后回归，100图已经看过成绩；正式采用前需要新的未参与调整的样本，并单独确认实际评价增加是否值得。Q1、r05源码与成绩不变，正式工作流不推进。','',
        '证据：图表/runs/20260924-A-q2-diagnosis-r06/（诊断与条件推演）；图表/runs/20260924-A-q2-reserve-r06-v2/（真实试验）；审查/证据/20260924-A-q2-diagnosis-r06/（失败、资源、传输及定位）。']
    p=ROOT/'审查/问题二结构准入退步诊断_r06.md';assert not p.exists();p.write_text('\n'.join(report)+'\n',encoding='utf-8')
    item=dict(status='diagnostic_candidate_not_promoted',report=p.relative_to(ROOT).as_posix(),summary=s,checks_sha256=sha(dest.read_bytes()),
              sources={n:sha((ROOT/'程序'/n).read_bytes()) for n in ['q2_route_diagnosis.py','q2_reserve_gate.py','q2_reserve_campaign.py','q2_reserve_campaign_v2.py','q2_reserve_counterfactual.py','q2_diagnosis_report.py']})
    for rel in ['图表/全部结果.json','程序/code_manifest.json']:
        p=ROOT/rel;v=read(p);assert 'q2_diagnosis_r06' not in v;v['q2_diagnosis_r06']=item;write_json(p,v)
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:f.write('\n\n## Q2 r06退步诊断\n\n16个退步均有基础候选损失，先修准入而非J。重复名额回收的14图回归结果：'+str(s['outcomes'])+'；为事后回归，非独立确认，未替换r05默认。详细周期、搬运、实际评价与耗时见审查/问题二结构准入退步诊断_r06.md。失败验证目录另存，Q1和r05成绩未改。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:f.write('\n| 2026-09-24 | Codex | Q2候选机会损失诊断、重复名额回收与14图回归 | r05全部保存轨迹及原始官方B | 保留失败断言与JSON键类型定位；未称独立确认，未改默认 | 待指定 |\n')
    print(json.dumps(dict(changed=len(changed),outcomes=s['outcomes'],report=str(ROOT/'审查/问题二结构准入退步诊断_r06.md')),ensure_ascii=False))


if __name__=='__main__':main()
