"""Publish Q3's verified index, narrative, source manifest and figure references."""
import json
from pathlib import Path
from q1_io import ROOT,sha,write_json


def main():
    run=ROOT/'图表/runs/20260924-A-q3-full-r02'
    out=ROOT/'图表/runs/20260924-A-q3-delivery-r03'
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    checks=json.loads((run/'verification.json').read_text(encoding='utf-8'))
    assert checks['passed'] and checks['count']==500
    rows=json.loads((run/'progress.json').read_text(encoding='utf-8'))
    changes=sum(r['selected_l2_added']!=r['no_l2_added'] for r in rows)
    delta=summary['selected_total_added']-summary['baseline_total_added']
    report=['# 问题三：共享L2模型、百图求解与核验', '',
      '基于main f8931b56与Q2 r07（c47a5986），已完成100图×1～5核的500组成对实验。输入、配置与官方评估器保持原始字节；所有无L2结果重新评价并与Q2冻结指标一致。工作分支codex/q3-model-solve，正式阶段门禁及人工接收未推进。', '',
      '## 模型与实际采用算法', '',
      '采用“共享FIFO缓存约束下的多处理器调度离散事件优化模型”，继承Q2划分、分核与核内排序。新增共享FIFO状态及DDR/L2两个独立公平带宽池。查询发生在COPY_IN发射，填充发生在完成；命中不刷新FIFO顺序，并发冷读不合并。所有合资格COPY_IN均可查询，包含spill reload与跨核中间张量，L2命中不能绕过500周期同步、Pipe和L1/UB约束。详见建模报告问题三节。', '',
      '以Q2 r07方案为可行种子，按真实重复未命中字节优先选择子图，保留普通关键度排序作为后备；在合法区间尝试迁移/插入。每配置最多评价4个新增候选，按周期优先、同周期少逻辑额外搬运接受。最终胜出方案重新调用原始官方Q3逐字段核验。只保证不劣于已评价L2种子，未提供全局最优或局部收敛证书。', '',
      '开发集case001/005/019、核数1/3/5共9组；同预算普通邻域对照中，引导策略2胜6平1负，不能据此声称普遍更优。将预算4增加到12，9组采用周期均相同。邻域惰性实现的18组至多12候选与原实现逐字段、逐顺序一致。', '',
      '## 五点主结果', '',
      '以下均为100个逐例比值的算术平均，不是总周期比。前三列共同使用无L2单核周期作为分母；后两列使用相同核数的无L2周期作分子。问题三单核相对缓存收益按真实模拟计算，不人为固定为1。', '',
      '|核数|无L2加速比|同方案L2加速比|优化L2加速比|同核硬件时间比|同核综合时间比|新增搜索改善数|',
      '|---|---|---|---|---|---|---|']
    for c in summary['curve']:
        report.append('|'+str(c['cores'])+'|'+ '|'.join(f"{c[k]:.6f}" for k in ['no_l2_speedup','fixed_l2_speedup','selected_l2_speedup','hardware_ratio','combined_ratio'])+f"|{c['search_wins']}|")
    report += ['',f"新增搜索共改善{summary['total_search_improved']}组周期，对其余配置保留不劣方案；同方案启用L2存在{len(summary['hardware_losses'])}组退步，优化后仍有{len(summary['combined_losses'])}组比无L2慢。完整正负结果见pairs.csv，不删除反例。",'',
      f"500组逻辑额外搬运合计：基线{summary['baseline_total_added']} bytes，优化L2为{summary['selected_total_added']} bytes，差值{delta:+d} bytes，涉及{changes}组变化。主要目标为周期，次要搬运不保证同时改善。相同方案在B与L2下的逻辑搬运字典完全相同；实际DDR服务字节的辅助指标才扣除命中字节。",'',
      '## 机制、容量与带宽', '',
      'case044单核从154407降至107814周期，时间比1.432161；216次命中、4408416命中字节全部为spill reload。其容量0/64/128/256/512/1024/2048 KiB下周期依次为154407/154272/154407/154407/134726/107814/107814，表现为明显阈值与小幅非单调。case046的144次命中也全部来自reload。两例为事后机制诊断，不是独立确认集。', '',
      'case005五核的命中字节190764来自原始输入、183552来自跨核输入。固定Q2方案下L2带宽60/125/250/500 bytes/cycle时周期为48200/48202/48259/48253。带宽变化会改变后续查询与并发集合，不能强制单调；上述扫描仅为诊断，所有主成绩坚持1MiB、250 bytes/cycle。', '',
      '固定配置最明显退步是case067双核：32040130→32217720周期，增加177590（约0.5543%）。观察关键路径重构误差为0；两条路径的Cube与Vector计算时间相同，差值集中于搬运关键路径，从1476930变为1654520周期。这是固定执行的解释，不是反事实因果节省估计。', '',
      '## 检查与复现', '',
      f"全量检查：500组覆盖和无L2冻结指标、1000份FIFO事件账本、500份胜出方案全局物理内存审计，以及{checks['additional_changed_anchor_memory_audits']}份改变方案时原L2种子的额外全局容量审计。跨核释放和搬运恒等式通过，所有胜出方案独立官方重放相同。", '',
      '单元测试覆盖并发冷读不合并、零容量/超大张量旁路、真实命中、指标守恒与确定性。case001双核冷启动已通过，直接官方CLI的全部计算字段相同；CLI仅增加input_graph/input_plan文件名元数据。Linux Python3.12.14服务器12进程；本机Python3.14.6。候选预算不含已继承Q2搜索成本，冷启动另行记录。', '',
      '```text',
      'python 程序/主程序.py prepare',
      'python 程序/q3_submit.py 数据/processed/q1/data/case_005.json -n 3 --seed 图表/runs/20260924-A-q2-delivery-r07/solutions/3cores/case_005_multicore_res.json --output new-q3-check',
      'python 程序/q3_campaign.py --workers 1 --budget 4 --output new-q3-full',
      'python 程序/q3_verify.py --run new-q3-full --output new-q3-full/verification.json',
      '```', '',
      '输出目录必须新建；并行数按资源检查决定。求解仅Python标准库；重新制图需Matplotlib与中文字体。完整结果目录为图表/runs/20260924-A-q3-full-r02，曲线及逐例附录在q3-delivery-r02；开发消融、参数诊断和负例解释均保留独立目录。', '',
      '## 文献与限制', '',
      '本地SIGMA和T10仅支持通信/负载/内存耦合的背景思路，没有直接移植其模型或数值。FIFO非单调背景核对了IBM Research所列Belady等1969论文：https://research.ibm.com/publications/an-anomaly-in-space-time-characteristics-of-certain-programs-running-in-a-paging-machine 。参考工程的Q2固定计划对照口径被采用，结果重新基于本仓库r07计算。', '',
      '官方100图是完整测试集的回归结果，不是未见泛化保证；新增步骤固定Q2划分并调整映射/排序，未穷举新划分。模拟周期不是硬件实测，求解墙钟受机器负载影响。正式论文、AI披露、团队人工验收仍由既定流程处理。']
    text='\n'.join(report)+'\n'
    (ROOT/'审查/问题三共享L2模型与百图求解.md').write_text(text,encoding='utf-8')
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:f.write('\n\n'+text.replace('# 问题三：','## 问题三：',1))
    index=json.loads((ROOT/'图表/全部结果.json').read_text(encoding='utf-8'))
    index.setdefault('model_identity',{})['Q3']=dict(academic_name='共享FIFO缓存约束下的多处理器调度离散事件优化模型',canonical_model_family='多处理器调度与离散事件仿真优化',solver_algorithm='Q2种子保护的缓存事件引导有界邻域搜索')
    index['question_3_r02']=dict(status='computed_and_checked_not_formal_gate',summary=summary,run=run.relative_to(ROOT).as_posix(),delivery=out.relative_to(ROOT).as_posix(),
        evidence=[dict(path=x.relative_to(ROOT).as_posix(),sha256=sha(x.read_bytes())) for x in [run/'progress.json',run/'contract.json',run/'verification.json',out/'summary.json']])
    write_json(ROOT/'图表/全部结果.json',index)
    manifest=json.loads((ROOT/'程序/code_manifest.json').read_text(encoding='utf-8'))
    newpaths=list((ROOT/'程序').glob('q3*.py'))+[ROOT/'程序/tests/test_q3.py',ROOT/'程序/主程序.py']
    names={x.relative_to(ROOT).as_posix() for x in newpaths}
    manifest['files']=[x for x in manifest['files'] if x['path'] not in names]+[dict(path=x.relative_to(ROOT).as_posix(),lines=len(x.read_text(encoding='utf-8-sig').splitlines()),sha256=sha(x.read_bytes()),role='Q3 core' if x.name in ['q3_solver.py','q3_neighborhood.py','q3_submit.py'] else 'Q3 support') for x in newpaths]
    manifest['q3_current_delivery_r02']=dict(entry='程序/q3_submit.py',batch='程序/q3_campaign.py',budget=4,dependency='Python standard library; plotting uses matplotlib',run=run.relative_to(ROOT).as_posix())
    write_json(ROOT/'程序/code_manifest.json',manifest)
    figures=json.loads((ROOT/'图表/figure_manifest.json').read_text(encoding='utf-8'))
    captions={'speedup':'无L2与只读L2的五点对照（共同无L2单核分母）','cache_gain':'同核L2硬件收益与综合收益','singlecore_capacity':'case044单核容量阈值与FIFO非单调','sensitivity':'case005容量与带宽诊断'}
    for name,claim in captions.items():
        path=(out/f'{name}.pdf').relative_to(ROOT).as_posix()
        figures['figures'].append(dict(path=path,claim=claim,source=(out/'pairs.csv').relative_to(ROOT).as_posix() if name in ['speedup','cache_gain'] else '图表/runs/20260924-A-q3-sensitivity-r01/rows.json' if name=='sensitivity' else '图表/runs/20260924-A-q3-cache-mechanism-r02/singlecore_capacity.json',reader_task='比较周期收益并辨识机制边界',publish=name!='sensitivity',placement='body' if name!='sensitivity' else 'diagnostic'))
    write_json(ROOT/'图表/figure_manifest.json',figures)
    with (ROOT/'图表/图表引用.tex').open('a',encoding='utf-8') as f:
        for name,caption in captions.items():
            if name=='sensitivity':continue
            f.write('\n'+r'\begin{figure}[!htbp]'+'\n'+r'\centering'+'\n'+r'\includegraphics[width=0.85\linewidth,height=0.70\textheight,keepaspectratio]{'+(out/f'{name}.pdf').relative_to(ROOT).as_posix()+'}\n'+r'\caption{'+caption+'}'+r'\label{fig:q3-'+name+'}\n'+r'\end{figure}'+'\n')
    print('Published Q3 evidence index and narrative')


if __name__=='__main__':main()
