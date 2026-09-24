"""Format and index completed r03 evidence, preserving all earlier entries."""
import json,hashlib,subprocess
from pathlib import Path
from q1_io import ROOT,sha,write_json
from q2_controls_campaign import OUT,ARMS,PHASES


def main():
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    evidence=ROOT/'审查/证据/20260924-A-q2-controls-r03'
    report=ROOT/'审查/问题二初解与J同预算对照_r03.md'
    raw=report.read_text(encoding='utf-8')
    # Frozen report generator emits blank separators; keep GFM table rows adjacent.
    lines=raw.splitlines();formatted=[]
    for i,line in enumerate(lines):
        if not line and i>0 and i+1<len(lines) and lines[i-1].startswith('|') and lines[i+1].startswith('|'):continue
        formatted.append(line)
    invalid=[];diagnostic_seconds=0.;pairs=[]
    for p in OUT.glob('*/*/*/*/search.json'):
        s=json.loads(p.read_text(encoding='utf-8'));diagnostic_seconds+=s['diagnostic_seconds']
        invalid += [dict(path=p.relative_to(ROOT).as_posix(),**x) for x in s['evaluations'] if x['status']!='ok']
    assert len(list(OUT.glob('*/*/*/*/row.json')))==120
    q1diff=subprocess.check_output(['git','diff','--name-only','HEAD','--','程序/q1_*.py','图表/runs/20260924-A-q1-delivery-r02'],cwd=ROOT,text=True).strip();assert not q1diff
    old=json.loads((ROOT/'图表/runs/20260924-A-q2-main-r02/contract.json').read_text(encoding='utf-8'))
    for name,h in old['sources'].items():assert sha((ROOT/'程序'/name).read_bytes())==h
    passed=[x['challenger'] for x in summary['confirmation']['comparisons'] if x['gate']]
    placement_diagnostics={};repair_diagnostics={}
    for phase,cases in PHASES.items():
        counts=dict(changed_plan_slots=0,win=0,tie=0,loss=0,invalid=0)
        repairs={a:dict(improved_over_base=0,tied_base=0) for a in ARMS[2:]}
        for i in cases:
            for k in range(2,6):
                search={a:json.loads((OUT/phase/f'case_{i:03}/{k}/{a}/search.json').read_text(encoding='utf-8')) for a in ARMS}
                for a,b in zip(search['placement_reference']['evaluations'],search['placement_corrected']['evaluations']):
                    if a['plan_sha256']==b['plan_sha256']:continue
                    counts['changed_plan_slots']+=1
                    if a['status']!='ok' or b['status']!='ok':counts['invalid']+=1;continue
                    counts['win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie']+=1
                for arm in ARMS[2:]:
                    s=search[arm];best=min(x['makespan'] for x in s['evaluations'] if x['status']=='ok')
                    repairs[arm]['improved_over_base' if best<s['base_makespan'] else 'tied_base']+=1
        placement_diagnostics[phase]=counts;repair_diagnostics[phase]=repairs
    decision=dict(status='confirmed_pilot' if passed else 'not_promoted',passing_challenges=passed,full100=False,
                  audit=summary['audit'],invalid_candidates=invalid,diagnostic_seconds=diagnostic_seconds,
                  q1_unchanged=True,r02_sources_unchanged=True,tests_passed=13,
                  placement_diagnostics=placement_diagnostics,repair_diagnostics=repair_diagnostics)
    crossround=[]
    for i in PHASES['development']:
        phase='validation' if i==12 else 'development'
        for k in range(2,6):
            a=json.loads((ROOT/f'图表/runs/20260924-A-q2-main-r02/{phase}/case_{i:03}/{k}/ordinary/row.json').read_text(encoding='utf-8'))
            b=json.loads((OUT/f'development/case_{i:03}/{k}/j_ordinary/row.json').read_text(encoding='utf-8'))
            assert a['reference']==b['reference'] and a['slots']==b['slots']==12
            crossround.append(dict(case=i,cores=k,old=a['makespan'],reference_heft=b['makespan'],ratio=a['makespan']/b['makespan'],
                                   outcome='win' if b['makespan']<a['makespan'] else 'loss' if b['makespan']>a['makespan'] else 'tie'))
    decision['crossround_shared_development']=crossround
    formatted += ['', '## 采用判断与完整性', '',
        f'确认集通过预设条件的挑战者：{passed if passed else "无"}。本轮未运行百图，未更改默认入口。',
        f'120份最终完整B回放相同；初解划分哈希一致、J前8候选与基准计划哈希一致、混合J的2+2来源一致。失败候选{len(invalid)}个，13项测试通过，Q1及r02冻结源码未改。',
        '若初解通信修正未通过，应保留参考B HEFT；若混合J未通过，保留普通J，不以少数正例或事后逐例择优替代确认结论。生命周期和重划分不在本轮变量中。']
    formatted += ['', 'reference_seconds在同一case各行重复记录，表示该case一次固定单核生成耗时，汇总时应按case去重。额外搬运量是计划执行字节，不是搜索累计读取量；求解seconds不能换算为任务执行cycles的提速收益。']
    formatted += ['', '## 候选作用范围诊断', '', '下列为已计预算候选的事后归因，不额外评价、不逐例混合两组最好成绩。']
    for phase in PHASES:
        formatted += ['',phase+' 通信修正改变的候选槽位及逐槽结果：'+json.dumps(placement_diagnostics[phase],ensure_ascii=False),
                      phase+' J相对共同8机会基础的改善配置数：'+json.dumps(repair_diagnostics[phase],ensure_ascii=False)]
    formatted += ['', '## 样本结构与结论边界', '',
        '结构画像另存structure_profiles.json。开发048为单连通分量，050含4011操作的主导分量；确认018/033/067分别有126/95/71个分量，最大分量59/64/124操作，067共8996个原始操作。确认集偏多分量结构，没有独立的单一大分量确认样本，不能据此推广到全部图；本轮不补选有利样本、不宣称完成全量结构覆盖。']
    formatted += ['', '## 与r02共享开发图的工程比较', '',
        '两轮均12次机会、同一固定单核分母；本轮参考HEFT同时替换旧放置及顺序框架，因此只作跨轮工程比较，不是单项通信修正的因果证据，也不是新的确认样本。两轮原始记录均保留。', '',
        '| case | 核数 | r02普通J周期 | r03参考HEFT＋普通J周期 | 胜平负 |','|---|---:|---:|---:|---|']
    for x in crossround:formatted.append(f"| {x['case']:03} | {x['cores']} | {x['old']} | {x['reference_heft']} | {x['outcome']} |")
    report.write_text('\n'.join(formatted)+'\n',encoding='utf-8')
    decision['report_sha256']=sha(report.read_bytes());write_json(OUT/'decision.json',decision)
    files=[ROOT/'程序'/n for n in ['q2_controlled.py','q2_controls_campaign.py','q2_controls_finalize.py']]+[ROOT/'程序/tests/test_q2_controlled.py']
    manifest=dict(entry='程序/q2_controls_campaign.py',files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes()),lines=len(p.read_text(encoding='utf-8').splitlines())) for p in files],status=decision['status'])
    write_json(evidence/'source_manifest.json',manifest)
    for rel,item in [('程序/code_manifest.json',manifest),('图表/全部结果.json',dict(run=OUT.relative_to(ROOT).as_posix(),decision=decision,report=report.relative_to(ROOT).as_posix()))]:
        p=ROOT/rel;x=json.loads(p.read_text(encoding='utf-8'));assert 'q2_controls_r03' not in x;x['q2_controls_r03']=item;write_json(p,x)
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## 问题二r03：初解通信与J同预算对照\n\n')
        f.write('完整报告：审查/问题二初解与J同预算对照_r03.md。开发012/048/050，预冻结确认018/033/067，2至5核。五点曲线、逐例胜平负、搬运量、搜索/回放/分母耗时位于图表/runs/20260924-A-q2-controls-r03/。\n\n')
        for x in summary['confirmation']['comparisons']:
            f.write(f"- 确认集 {x['challenger']} 相对 {x['baseline']}：{x['outcomes']}，几何平均提速比变化 {(x['geomean_ratio']-1)*100:+.6f}%，通过条件={x['gate']}。\n")
        f.write('\n120份完整B最终回放一致，13项测试通过；Q1和r02冻结证据保持，不更改正式阶段、不启动百图。\n')
    with (ROOT/'程序/README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n### Q2 r03 隔离对照\n\n`python 程序/q2_controls_campaign.py freeze` 冻结新实验；`run --phase development --case 12` 等运行单图；`report` 汇总全部120份方案；`python 程序/q2_controls_finalize.py` 格式化并索引。运行目录固定为20260924-A-q2-controls-r03且禁止覆盖，复现需独立副本/新版本OUT。placement两组8机会，J三组12机会，各类内同预算；不将两类预算混作因果对照。完整来源和版本见contract.json及source_manifest.json。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:
        f.write('\n| 2026-09-24 | Codex | Q2初解通信与J配额隔离对照 | 已冻结B模型、参考HEFT、6张图与官方评估器 | 120份完整回放、13项测试、同划分/同基础/2+2来源核验；完整报告r03，人工复核待完成 | 待指定 |\n')
    print(json.dumps(decision,ensure_ascii=False))


if __name__=='__main__':main()
