"""Bind full r07 confirmation and shared-preparation evidence without promotion."""
import csv,json
from q1_io import ROOT,sha,write_json
from q2_evaluator import key
from q2_full_campaign import OUT as BASE,read
from q2_full_r07_campaign import OUT,PILOT

def change(a,b):return (b/a-1)*100

def main():
    s=read(OUT/'summary.json');prediction=read(ROOT/'图表/runs/20260924-A-q2-diagnosis-r06/conditional_reserve.json')
    concordance=0
    for p in prediction['records']:
        d=OUT/f"cases/case_{p['case']:03}/{p['cores']}/fast"
        assert key(read(d/'plan.json'))==p['expected_plan_sha256'] and read(d/'row.json')['makespan']==p['expected_makespan'];concordance+=1
    frozen={}
    for v in ['20260924-A-q2-full-r05','20260924-A-q2-overhead-r07','20260924-A-q2-full-r07-shared-r08']:
        c=read(ROOT/'图表/runs'/v/'contract.json');assert all(sha((ROOT/'程序'/n).read_bytes())==h for n,h in c['sources'].items()),v;frozen[v]=True
    historical=read(ROOT/'图表/runs/20260924-A-q2-diagnosis-r06/source_manifest.json')
    assert all(sha((ROOT/p).read_bytes())==h for p,h in historical['files'].items())
    assert sha((BASE/'summary.json').read_bytes())==historical['source_summary_sha256']
    old=[];new=[];per_core={}
    for k in range(2,6):
        a=[read(BASE/f'cases/case_{i:03}/{k}/routed/row.json') for i in range(1,101)]
        b=[read(OUT/f'cases/case_{i:03}/{k}/fast/row.json') for i in range(1,101)]
        old.extend(a);new.extend(b);per_core[str(k)]={arm:{metric:sum(r[metric] for r in rows) for metric in ['makespan','bytes']} for arm,rows in [('r05',a),('r07',b)]}
    metrics={arm:{k:sum(r[k] for r in rows) for k in ['makespan','bytes','official_calls']} for arm,rows in [('r05',old),('r07',new)]}
    a,b=s['paired14_timing']['fast'],s['paired14_timing']['shared']
    checks=dict(frozen_sources=frozen,r05_historical_records_unchanged=len(historical['files']),conditional_prediction_full_plan_and_cycles_match=concordance,per_core_totals=per_core,totals=metrics,
        shared_search_seconds_change=change(a['solve_seconds'],b['solve_seconds']),shared_candidate_seconds_change=change(a['candidate_seconds'],b['candidate_seconds']),
        artifact_sizes={p:(ROOT/p).stat().st_size for p in ['计算结果.md','程序/主程序.py']})
    write_json(OUT/'final_checks.json',checks)
    with (OUT/'five_point_curve.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['cores','r05','r07'])
        for k in range(1,6):w.writerow([k,s['curves']['r05'][str(k)],s['curves']['r07'][str(k)]])
    report=['# 问题二r07官方100图确认与共享准备r08','','本轮完成冻结r07的官方100图实跑；共享准备另存r08，不覆盖r05/r06/r07源文件、历史成绩或默认交付。属于全量回归确认，非未见样本验证。','',
        '## 官方100图确认','',
        '固定官方输入、配置、迁移计划、种子0与每配置12次B机会；400配置均重新求解并另做官方最终回放。100个固定单核分母由已固定的精确引擎重新计算，与规定分母一致。五点曲线取100个逐图T1/Tk的算术平均，不是总周期之比；执行周期、额外搬运与求解耗时分别记录。','',
        f"相对r05：{s['outcomes']}，任务周期比值几何均值提升{(s['geomean_ratio']-1)*100:.6f}%。全部400份方案哈希及周期与此前条件推演一致；现在由真实全量求解确认，不再仅为历史轨迹推演。",'',
        '| 核数 | r05平均加速比 | r07平均加速比 |','|---|---:|---:|']
    for k in range(1,6):report.append(f"| {k} | {s['curves']['r05'][str(k)]:.6f} | {s['curves']['r07'][str(k)]:.6f} |")
    x,y=metrics['r05'],metrics['r07']
    report += ['',f"400配置周期合计{x['makespan']}→{y['makespan']}（{change(x['makespan'],y['makespan']):+.6f}%）；额外搬运字节{x['bytes']}→{y['bytes']}（{change(x['bytes'],y['bytes']):+.6f}%）。实际搜索评价{x['official_calls']}→{y['official_calls']}；机会均4800次，机会相等不代表实际调用相等。",'',
        f"最差配置记录：{s['worst']}。所有逐例胜平负、周期和搬运见pairs.csv；每核汇总见final_checks.json。r05历史运行与本轮主机负载不同，不用两批搜索秒数宣称工程提速。",'',
        '## 共享准备的工程效果','',
        'r08在单次候选生成中共用一份GraphModel和SceneBGraph，连通分量、混合划分、链划分和深度划分仅准备一次；旧放置与参考HEFT仍按原公式分别执行。复用仅发生于本次输入/配置/核数上下文，不复用跨问题评价结果，不改变J或增加搜索名额。','',
        '100图400配置的共享菜单名称、计划哈希和顺序逐项一致；固定14图56配置另做新旧完整求解，所有12条评价轨迹（含缓存命中）、最终完整方案及完整官方结果一致。共享版本未对其余344配置另做完整求解，不能称其已全量实跑。另64种小图组合通过菜单等价与原始输入不变检查，包含单节点触发的候选填充边界。','',
        '| 指标（同轮14图配对） | r07 | 共享r08 | 变化 |','|---|---:|---:|---:|']
    for label,k in [('候选准备秒数','candidate_seconds'),('搜索墙钟秒数合计','solve_seconds'),('真实搜索评价','official_calls')]:report.append(f'| {label} | {a[k]:.6f} | {b[k]:.6f} | {change(a[k],b[k]):+.3f}% |')
    report += ['',f"本轮r07候选准备仅占搜索耗时{a['candidate_seconds']/a['solve_seconds']*100:.3f}%，因此单独压缩这一环节对总耗时的改善空间有限。总耗时变化{change(a['solve_seconds'],b['solve_seconds']):+.3f}%是本次观测，不能据此认定稳定或显著的整体提速。",'',
        '计时采用服务器8独立进程、长图优先动态分配，14图内交替两方案顺序。为一次配对批次，负载波动仍影响计时；秒数合计不是整批用时或CPU时间。菜单等价审计、单核分母计算、最终回放、容量复核均不计入搜索秒数。','',
        f"官方最终回放共456次，400份r07真实全局张量生命周期容量复核通过；候选非法数{len(s['checks']['invalid_candidates'])}。正式阶段与人工门禁未推进。",'',
        '## 复现与交接','',
        '入口：python 程序/q2_full_r07_campaign.py freeze；python 程序/q2_full_r07_campaign.py launch --workers 8；python 程序/q2_full_r07_campaign.py report；python 程序/q2_full_r07_finalize.py。运行目录拒绝覆盖；重跑应新增证据目录。服务器Python3.12.14，资源快照、源码/输入/迁移计划哈希见contract.json与execution.json。','',
        'r07算法收益与r08工程收益分开解释。此轮不自动替换r05默认或重写冻结写作交接；如采用新版本，须明确新增搬运代价并同步交付入口、支撑材料与B端写作证据。未见真实样本确认仍单独保留，不用官方100图回归冒充。']
    path=ROOT/'审查/问题二r07全量确认与共享准备_r08.md';assert not path.exists();path.write_text('\n'.join(report)+'\n',encoding='utf-8')
    item=dict(status=s['status'],report=path.relative_to(ROOT).as_posix(),summary_sha256=sha((OUT/'summary.json').read_bytes()),checks_sha256=sha((OUT/'final_checks.json').read_bytes()),sources={n:sha((ROOT/'程序'/n).read_bytes()) for n in ['q2_reserve_shared.py','q2_full_r07_campaign.py','q2_full_r07_finalize.py','tests/test_q2_shared_preparation.py']})
    for rel in ['程序/code_manifest.json','图表/全部结果.json']:
        p=ROOT/rel;d=read(p);assert 'q2_full_shared_r08' not in d;d['q2_full_shared_r08']=item;write_json(p,d)
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:f.write('\n\n## Q2 r07全量确认与r08共享准备\n\n官方100图r07重新求解并回放，相对r05：'+str(s['outcomes'])+'。共享菜单400配置一致，完整求解等价验证56配置。周期、搬运、实际评价和同轮工程计时分别见审查/问题二r07全量确认与共享准备_r08.md。未改默认及问题一冻结成绩。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:f.write('\n| 2026-09-24 | Codex | Q2 r07官方全量确认、r08共享准备与等价审计 | 固定官方B实跑及全局生命周期 | 全量回归非未见确认；未自动改默认及B/C交接 | 待指定 |\n')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
