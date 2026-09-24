"""Append full100 evidence without replacing Q1 or earlier Q2 records."""
import json, subprocess
from q1_io import ROOT, sha, write_json
from q2_full_campaign import OUT, read


def main():
    s=read(OUT/'summary.json');a=read(OUT/'full_audit.json');d=OUT/'delivery'
    assert a['results']==800 and (d/'manifest.json').is_file()
    assert not subprocess.check_output(['git','diff','--name-only','HEAD','--','程序/q1_*.py','图表/runs/20260924-A-q1-delivery-r02'],cwd=ROOT,text=True).strip()
    sources=[ROOT/'程序'/n for n in ['q2_full_campaign.py','q2_full_audit.py','q2_full_delivery.py','q2_r05_submit.py','q2_full_package.py','q2_full_index.py','q2_import_full.py']]
    source_manifest=dict(entry='程序/q2_r05_submit.py',files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes()),lines=len(p.read_text(encoding='utf-8').splitlines())) for p in sources])
    decision=dict(status='full100_computational_evidence_checked_not_formal_acceptance',selected=s['selected_global_algorithm'],summary=s,
                  audit_path=(OUT/'full_audit.json').relative_to(ROOT).as_posix(),audit_sha256=sha((OUT/'full_audit.json').read_bytes()),
                  delivery_manifest=(d/'manifest.json').relative_to(ROOT).as_posix(),q1_unchanged=True,formal_stage_advanced=False,old_default_changed=False)
    for rel,new in [('程序/code_manifest.json',source_manifest),('图表/全部结果.json',decision)]:
        p=ROOT/rel;value=read(p);assert 'q2_full_r05' not in value;value['q2_full_r05']=new;write_json(p,value)
    p=ROOT/'图表/figure_manifest.json';value=read(p)
    value['figures'].append(dict(path=(d/'five_point_curve.pdf').relative_to(ROOT).as_posix(),claim='100图规定单核基准下，各核逐图加速比的算术平均；两算法同预算对照。',source=(OUT/'summary.json').relative_to(ROOT).as_posix(),reader_task='比较1至5核与结构准入效果',publish=False,placement='body',status='review_ready_pending_manuscript_integration'))
    write_json(p,value)
    with (ROOT/'图表/图表引用.tex').open('a',encoding='utf-8') as f:
        f.write('\n% Q2 r05: review-ready; include after B/C layout verification.\n'+r'\begin{figure}[!htbp]'+'\n'+r'\centering'+'\n'+r'\includegraphics[width=0.72\linewidth,height=0.70\textheight,keepaspectratio]{图表/runs/20260924-A-q2-full-r05/delivery/five_point_curve.pdf}'+'\n'+r'\caption{场景B下100个算例的平均加速比。同一规定单核基准，按逐例比值取算术平均。}'+'\n'+r'\label{fig:q2-r05-mean-speedup}'+'\n'+r'\end{figure}'+'\n')
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## 问题二r05全量验证\n\n'+f"统一选择{s['selected_global_algorithm']}。100图×2～5核×两算法，每组12机会；胜平负{s['outcomes']}，几何平均相对变化{(s['geomean_ratio']-1)*100:+.6f}%。规定五点算术平均曲线：{s['curves']}。800次最终回放一致，选定400方案真实全局驻留核验通过。详见图表/runs/20260924-A-q2-full-r05/delivery/report.md；未提前剔除退步例，未改变Q1成绩。搜索时间不含迁移种子生成、固定单核及最终回放；正式论文与人工验收仍未完成。\n")
    with (ROOT/'建模报告.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## 问题二r05采用边界\n\n'+f"本轮统一采用算法为{s['selected_global_algorithm']}，数值由100图同预算实验决定。仍继承既有场景B模型。实际求解使用结构初解和普通有界J；结构准入仅按预冻结条件选择是否采用。上文关键链引导、修正通信代理、生命周期面积是研究机制与诊断，不代表全部进入最终算法，不能写成已验证的收益来源。题面正式输入不含Op-Op边。图表/全部结果.json的q2_full_r05为当前计算证据；不改Q1模型及成绩。\n")
    with (ROOT/'程序/README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n### Q2 r05 全量复现\n\n新入口`q2_r05_submit.py`读取固定全量决策；传入`--migration`复现共同预生成种子的对照，省略时从原图生成Q1种子并单独记录额外12次A机会及耗时。旧`q2_submit.py`默认保持历史版本。完整命令和时间口径见`output/q2-r05-portable/README.md`，先运行包内`verify_package.py`。全量800结果、400选定方案容量核验及500行指标见`图表/runs/20260924-A-q2-full-r05/`。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:
        f.write('\n| 2026-09-24 | Codex | Q2同预算全量对照、实际驻留审计、表图及复现附件 | 原题与固定官方B、全部100图 | 800结果回放与400份真实容量检查；正式论文和人工验收未代填 | 待指定 |\n')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## 问题二当前计算证据 r05\n\n'+f"100图同预算对照统一选择`{s['selected_global_algorithm']}`。五点均值为"+'、'.join(f"{s['curves'][s['selected_global_algorithm']][str(k)]:.6f}" for k in range(1,6))+'。见[全量报告](图表/runs/20260924-A-q2-full-r05/delivery/report.md)、[要求审核](审查/问题二建模解算要求审核_r04.md)及[复现说明](output/q2-r05-portable/README.md)。保留全部退步例及搬运/耗时代价；正式章节、排版和人工验收仍未完成，Q1冻结证据未改。\n')
    write_json(OUT/'index_decision.json',decision)
    handoff=ROOT/'协作/交接/Q2/Q2-WRITE-r05-DRAFT.md';assert not handoff.exists();handoff.parent.mkdir(parents=True,exist_ok=True)
    handoff.write_text(f'''# Q2-WRITE-r05：A → B 写作资料草案

- 提交方A；接收方B操作者；状态DRAFT，未代填接收结论，未启动B/C。
- 分支codex/q2-compliance-r04；输入main为50b91d46a7bd43ca404c1285dfc27929496bf266。
- 产物提交SHA：NOT_COMMITTED，发布可访问产物版本后才能改READY；本机路径不作为团队下载入口。
- 正式工作流未推进，DISCOVERY未启动；计算核验不等于论文或人工验收。

## 已核对的计算依据

`图表/runs/20260924-A-q2-full-r05/summary.json`、`full_audit.json`、`delivery/manifest.json`、`delivery/report.md`。
100图×2～5核×两算法，12次B机会；800次独立最终回放，400份选定方案实际全局驻留检查。
最终统一选择{s['selected_global_algorithm']}，不得逐例拼接最好结果。
1～5核曲线：{s['curves'][s['selected_global_algorithm']]}。
胜平负：{s['outcomes']}，辅助几何平均比值{s['geomean_ratio']:.9f}。

## 写作主线与约束

场景A到B的变化 → 按消费核心去重的通信与跨子图物理驻留 → 划分、分核及顺序联合决策 → 结构初解与普通有界J → 全量实验与局限。
保持一个场景B扩展模型，不堆叠新的模型名称。官方B规则决定COPY、缓存溢出、Pipe和共享DDR；候选代理不是真实执行约束。
核心容量L1=524288、UB=131072字节，DDR总带宽60，跨核COPY完成后等待500周期。同核不沿用A的跨Task清空假设。
关键链引导J、修正通信代理与生命周期面积曾作研究，不能全部写成已采用机制。完整对照范围和负结果见r03/r04报告。
正文必须使用逐图T1/Tk的算术平均，不用总时间比或几何平均替代。单核为题目规定整图基准，不能优化分母。
搜索秒数不含预生成Q1种子、冷单核和最终回放；独立入口省略--migration时会生成种子，额外12次A机会单列。不能写成全部流程只有12次评价。

## 复现与版面接口

`output/q2-r05-portable/README.md`给出实际复现入口；先运行包内verify_package.py。
`delivery/selected_500_rows.csv`为全量附录数据，`delivery/appendix_table.tex`为500行长表接口，需longtable/booktabs。
`delivery/five_point_curve.pdf`为五点图，引用段在图表/图表引用.tex，当前为review_ready，待实际章节编译核对后采用。
先读审查/问题二建模解算要求审核_r04.md，再读r05报告中的全量补充；历史未完成状态不可改写成当时已完成。
保留全部退步例、搬运与耗时，不宣称全局最优或每例均改善。

## 后续与接收

A发布可访问的产物提交后给B；B在独立分支写问题二章节，再由C操作者核对格式和数值，A最终整合。
正文图最终字号、长表分页、引用及源码附录仍须编译检查；本草案未代替这一步。
接收人、接收SHA、验证命令、ACCEPTED/CHANGES_REQUESTED：由接收人填写。
''',encoding='utf-8')


if __name__=='__main__':main()
