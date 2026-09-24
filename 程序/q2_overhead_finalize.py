"""Publish only observed r07 results, explicitly separating synthetic validation."""
import csv,json
from q1_io import ROOT,sha,write_json
from q2_overhead_campaign import OUT,read

def pct(a,b):return (b/a-1)*100 if a else None

def main():
    s=read(OUT/'summary.json');old=read(OUT/'attribution.json');checks={}
    for version in ['20260924-A-q2-full-r05','20260924-A-q2-reserve-r06','20260924-A-q2-reserve-r06-v2','20260924-A-q2-overhead-r07']:
        c=read(ROOT/'图表/runs'/version/'contract.json')
        assert all(sha((ROOT/'程序'/n).read_bytes())==h for n,h in c['sources'].items()),version
        checks[version]=True
    a,b=s['regression']['totals']['reserve'],s['regression']['totals']['fast']
    assert a['makespan']==b['makespan'] and a['bytes']==b['bytes']
    pred=read(OUT/'cache_prediction.json');assert b['official_calls']==pred['predicted']
    inventory=read(ROOT/'审查/证据/20260924-A-q2-overhead-r07/external_input_inventory.json')
    allchecks=list(OUT.glob('*/*/*/checks.json'));assert len(allchecks)==96
    assert all(all(read(p)[k] for k in ['complete_plan_and_result_equal','anchor_and_J_equal','global_capacity_pass']) for p in allchecks)
    with (OUT/'five_point_curves.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['sample','arm','cores','mean_individual_speedup'])
        for sample in ['regression','synthetic']:
            for arm,curve in s[sample]['curves'].items():
                for k,value in curve.items():w.writerow([sample,arm,k,value])
    write_json(OUT/'final_checks.json',dict(frozen_sources=checks,paired_equivalence=96,global_capacity=96,cache_prediction_equal=True,
        official_external_files=len(inventory),external_new_hashes=sum(not r['known'] for r in inventory),official_unseen_confirmation=False,
        artifact_sizes={n:(ROOT/n).stat().st_size for n in ['计算结果.md','程序/主程序.py']},result_json_count=len(list((ROOT/'图表').glob('*.json')))))
    r=['# 问题二求解开销与新样本检验 r07','','本轮保持r06方案结果，优化工程实现；r05默认交付及问题一冻结成绩不变。正式工作流阶段不推进。','',
       '## 开销归因','',
       '原14图轨迹：r05搜索852.486秒，r06为1030.757秒，增加178.271秒。其中评价环节增加59.515秒，评价外剩余时间增加118.756秒。剩余时间含候选生成、J准备和记账，不能全部称为候选生成耗时。r06共643次真实评价，其中638个不同方案、5次缓存逐出后的重复评价。','',
       'r07复用首次生成的旧候选菜单，取消整套重复生成；保持未被使用的重复项在原相对位置，仅移除用于补位的最后几个重复项，再追加相同的旧候选。所有不同候选的首次出现顺序保持一致，严格比较的同分优先级不变；J规则、12机会预算、容量2的完整结果缓存均不变。未引入跨输入或跨评估版本的成绩缓存。','',
       '## 同机重新计时与结果等价','',
       '服务器4进程，两方案交替执行；14图×4核配置，r06与r07各56次新求解。搜索秒数为进程墙钟时间之和，不是批次总耗时或CPU秒。排除迁移种子生成、固定单核计算、最终回放与容量审计。','',
       '| 指标 | r06重跑 | r07 | 变化 |','|---|---:|---:|---:|']
    for label,k in [('任务周期合计','makespan'),('额外搬运字节合计','bytes'),('真实搜索评价次数','official_calls'),('搜索秒数合计','solve_seconds'),('评价环节秒数合计','assessment_seconds')]:
        r.append(f'| {label} | {a[k]:.3f} | {b[k]:.3f} | {pct(a[k],b[k]):+.3f}% |')
    r += ['',f"评价外剩余秒数：{a['solve_seconds']-a['assessment_seconds']:.3f} → {b['solve_seconds']-b['assessment_seconds']:.3f}。56配置的完整计划、完整官方结果、基础最优计划和4个J候选全部一致；真实调用数符合事先缓存轨迹预测{pred['predicted']}次。历史旧值与本轮新值不可混合计算工程提速。",'',
          '## 新合成样本：独立于本轮调参，非官方确认','',
          f"外部目录核查{len(inventory)}份原始图，均为已使用官方100图的重复副本，未找到未见官方输入。冻结实现和生成规则后，使用固定新种子生成10图：多分量、分叉汇合、分层随机依赖、容量压力，规模128/512节点，并增加两个2048节点图。全部先经官方图合法性检查，输入及生成器哈希固化在数据/processed/q2-synthetic-r07。没有根据此次胜负调整规则或删除失败/退步样本。",'',
          '三组使用同一新生成的Q1迁移计划；A侧生成12次预算与耗时单独记录，再按官方B重新评价。单核分母直接由官方单核程序重新计算。每组8基础+4普通J，最终均另做官方回放。新图仅检验合成结构上的适用性，不能替代真实分布的未见官方算例。','',
          '| 核数 | r05结构准入 | r06重复名额回收 | r07工程优化 |','|---|---:|---:|---:|']
    v=s['synthetic']
    for k in range(1,6):r.append('| '+str(k)+' | '+' | '.join(f"{v['curves'][arm][str(k)]:.6f}" for arm in ['routed','reserve','fast'])+' |')
    x,y=v['totals']['routed'],v['totals']['fast'];w=v['worst']
    r += ['',f"r07对r05逐例胜平负：{v['outcomes']}；任务周期比值的几何均值提升{(v['geomean_ratio']-1)*100:+.4f}%。额外搬运合计{x['bytes']}→{y['bytes']}（{pct(x['bytes'],y['bytes']):+.3f}%），周期合计{x['makespan']}→{y['makespan']}（{pct(x['makespan'],y['makespan']):+.3f}%）；搜索秒数{x['solve_seconds']:.3f}→{y['solve_seconds']:.3f}（{pct(x['solve_seconds'],y['solve_seconds']):+.3f}%）。这些是本合成集的真实结果，不能推算官方100图收益。",'',
          f"最差配置：{w['case']} / {w['cores']}核，{w['base_cycles']}→{w['fast_cycles']} cycles，周期变化{pct(w['base_cycles'],w['fast_cycles']):+.3f}%。所有逐例数据含平例及退步保存在synthetic_pairs.csv。",'',
          '40个新配置的r06/r07完整方案和结果相同，另40份r07全局张量驻留检查通过；连同回归共96份容量复核。候选非法数分别见summary.json，不能只检查最终方案就宣称所有候选合法。','',
          '## 采用边界与复现','',
          '工程改动的等价性与计时结果仅对本次已检查样本成立。计时为一次配对批次，存在共享服务器负载波动，不能将百分比视作稳定性能常数。r07没有新增模型收益，其周期/搬运应与r06相同。当前默认仍为r05；正式推广重复名额回收仍缺未见真实算例确认。后续拿到额外输入后，应冻结当前实现并一次性评估，不能把已用官方100图重新抽样称为独立确认。','',
          '命令：python 程序/q2_overhead_diagnosis.py；python 程序/q2_overhead_campaign.py freeze；python 程序/q2_overhead_campaign.py launch --workers 4；python 程序/q2_overhead_campaign.py report；python 程序/q2_overhead_finalize.py。freeze/launch拒绝覆盖已有运行；复现须使用新的输出目录，保留当前证据。','',
          '证据：图表/runs/20260924-A-q2-overhead-r07/；数据/processed/q2-synthetic-r07/；审查/证据/20260924-A-q2-overhead-r07/。所有耗时来自实际运行，未提前承诺收益。']
    p=ROOT/'审查/问题二开销优化与新样本检验_r07.md';assert not p.exists();p.write_text('\n'.join(r)+'\n',encoding='utf-8')
    item=dict(status=s['status'],report=p.relative_to(ROOT).as_posix(),summary_sha256=sha((OUT/'summary.json').read_bytes()),checks_sha256=sha((OUT/'final_checks.json').read_bytes()),sources={n:sha((ROOT/'程序'/n).read_bytes()) for n in ['q2_overhead_diagnosis.py','q2_reserve_fast.py','q2_overhead_campaign.py','q2_overhead_finalize.py']})
    for rel in ['程序/code_manifest.json','图表/全部结果.json']:
        p=ROOT/rel;d=read(p);assert 'q2_overhead_r07' not in d;d['q2_overhead_r07']=item;write_json(p,d)
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:f.write('\n\n## Q2 r07工程开销与合成检验\n\n14图回归及10张新合成图完成。96配置r06/r07完整结果一致，全局容量复核通过；不冒充未见官方确认，不改r05默认。详见审查/问题二开销优化与新样本检验_r07.md及绑定运行证据。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:f.write('\n| 2026-09-24 | Codex | Q2 r07开销归因、等价工程优化、冻结合成检验 | 既有轨迹与官方B实跑 | 新样本明确为合成，真实未见确认仍缺；旧结果不改 | 待指定 |\n')
    print(json.dumps(dict(regression_seconds_change=pct(a['solve_seconds'],b['solve_seconds']),synthetic=v['outcomes']),ensure_ascii=False))

if __name__=='__main__':main()
