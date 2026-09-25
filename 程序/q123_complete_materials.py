"""Fail-closed material refresh from the complete, hash-checked delivery matrix.

Run with a plotting/PDF Python. Does not promote formal workflow gates.
"""
import argparse,csv,gzip,hashlib,json,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from q23_completion_report import report
from q23_delivery_complete import read,sha
from q1_io import official,verify,write_json

ROOT=Path(__file__).resolve().parents[1]
RUN=Path('图表/runs/20260925-A-q23-requirements-completion')
OLD=Path('图表/runs/20260925-A-q23-full100-verified')
OUT=Path('图表/runs/20260926-A-q123-complete-delivery')

def text(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def num(x):return f'{x:,}'.replace(',',r'\,')
def figure(name,ys,ylabel):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':12,'axes.unicode_minus':False,'pdf.fonttype':42})
    f,a=plt.subplots(figsize=(5.8,3.6),layout='constrained')
    for (label,y),marker,style in zip(ys.items(),['o','s','^'],['-','--',':']):a.plot(range(1,6),y,marker=marker,linestyle=style,label=label)
    a.set(xlabel='核心数',ylabel=ylabel,xticks=range(1,6));a.grid(axis='y',alpha=.25);a.legend(fontsize=11)
    a.spines[['top','right']].set_visible(False);f.savefig(OUT/(name+'.pdf'));f.savefig(OUT/(name+'.png'),dpi=180);plt.close(f)

def table(headers,rows,caption,label):
    return '\n'.join([r'\begin{table}[!htbp]\centering\small',rf'\caption{{{caption}}}\label{{{label}}}',r'\begin{tabular}{'+'r'*len(headers)+'}',r'\toprule',' & '.join(headers)+r'\\',r'\midrule']+[' & '.join(map(str,r))+r'\\' for r in rows]+[r'\bottomrule',r'\end{tabular}',r'\end{table}'])+'\n'

def fig(name,caption,label):return rf'''
\begin{{figure}}[!htbp]\centering
\includegraphics[width=0.85\linewidth,height=0.70\textheight,keepaspectratio]{{../{OUT.as_posix()}/{name}.pdf}}
\caption{{{caption}}}\label{{{label}}}
\end{{figure}}
'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--compile',action='store_true');a=ap.parse_args()
    r=report(RUN,OLD)
    if not r['complete']:raise SystemExit('Coverage incomplete: paper and curves NOT promoted')
    cold=Path('图表/runs/20260926-A-q123-cold-audit')
    if not (cold/'complete.json').exists():raise SystemExit('Cold timing audit still running: paper NOT promoted')
    cold_local=Path('图表/runs/20260926-A-q123-cold-audit-local')
    while not (cold_local/'complete.json').exists():
        print('Waiting for local cold audit; paper NOT promoted',flush=True);time.sleep(60)
    verify();official();from stub_multicore_cut_and_schedule import validate_multicore_plan
    OUT.mkdir(parents=True,exist_ok=True);matrix={};manifest=[]
    for p in (OLD/'rows').glob('*.json'):
        x=read(p)
        if x['problem']==2:
            folder=OLD/'jobs'/f'q2_{x["case"]:03}';matrix[(2,x['case'],5)]=(x,folder/'final.plan.json',folder/'final.evaluation.json.gz',x['plan_file_sha256'],x['evaluation_file_sha256'])
    for p in (RUN/'rows').glob('*.json'):
        x=read(p);folder=RUN/'jobs'/p.stem
        matrix[(x['problem'],x['case'],x['cores'])]=(x,folder/f'case_{x["case"]:03}_multicore_res.json',folder/'evaluation.json.gz',x['plan_sha256'],x['evaluation_sha256'])
    assert len(matrix)==1000
    for (q,n,k),(x,pp,ep,ph,eh) in sorted(matrix.items()):
        assert x['valid'] and sha(pp)==ph and sha(ep)==eh,(q,n,k)
        p=read(pp);raw=read(Path(f'数据/processed/q1/data/case_{n:03}.json'));validate_multicore_plan(raw,p)
        assert set(p)=={'node_to_subgraph','core_schedules'} and len(p['core_schedules'])==k
        with gzip.open(ep,'rt',encoding='utf-8') as f:e=json.load(f)
        assert (e['makespan'],e['data_movement_bytes']['added_copy_bytes'])==(x['makespan'],x['added'])
        if q==3:
            with gzip.open(ep.parent/'same_plan_no_l2.json.gz','rt',encoding='utf-8') as f:plain=json.load(f)
            assert plain['makespan']==x['no_l2_makespan'] and plain['data_movement_bytes']['added_copy_bytes']==x['no_l2_added']==x['added']
            assert e['cache_stats']['hit_rate']==x['cache_hit_rate']
        target=OUT/'solutions'/f'q{q}'/f'{k}cores'/f'case_{n:03}_multicore_res.json';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pp,target)
        manifest.append(dict(problem=q,case=n,cores=k,plan=target.as_posix(),sha256=ph,evaluation=ep.as_posix(),evaluation_sha256=eh))
    q1=read(Path('图表/runs/20260924-A-q1-delivery-r02/aggregate.json'))
    for k in range(1,6):
        for n in range(1,101):
            p=Path(f'图表/runs/20260924-A-q1-delivery-r02/solutions/{k}cores/case_{n:03}_multicore_res.json')
            dest=OUT/'solutions'/'q1'/f'{k}cores'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
            plan=read(p);validate_multicore_plan(read(Path(f'数据/processed/q1/data/case_{n:03}.json')),plan);assert len(plan['core_schedules'])==k
            manifest.append(dict(problem=1,case=n,cores=k,plan=dest.as_posix(),sha256=sha(dest),evidence='20260924-A-q1-delivery-r02; prior official audit'))
    points={(p['problem'],p['cores']):p for p in r['points']};single=q1[0]['total_cycles'];comp={}
    for k in range(1,6):comp[k]=sum(matrix[(2,n,k)][0]['makespan']/matrix[(3,n,k)][0]['makespan'] for n in range(1,101))/100
    for q in (2,3):
        headers=['算例','核数','周期','额外搬运','加速比'] if q==2 else ['算例','核数','无 L2 周期','L2 周期','额外搬运','命中率']
        lines=[r'\begingroup\small\setlength{\tabcolsep}{3pt}',r'\begin{longtable}{'+'r'*len(headers)+'}',r'\toprule',' & '.join(headers)+r'\\\midrule\endhead']
        for k in range(1,6):
            for n in range(1,101):
                x=matrix[(q,n,k)][0]
                vals=[n,k,x['makespan'],x['added'],f'{x["single"]/x["makespan"]:.6f}'] if q==2 else [n,k,x['no_l2_makespan'],x['makespan'],x['added'],f'{x["cache_hit_rate"]:.6f}']
                lines.append(' & '.join(map(str,vals))+r'\\')
        lines += [r'\bottomrule\end{longtable}\endgroup'];text(OUT/f'q{q}_appendix.tex','\n'.join(lines)+'\n');shutil.copyfile(RUN/f'q{q}_appendix.csv',OUT/f'q{q}_appendix.csv')
    figure('speedup',{'问题一':[p['mean_speedup'] for p in q1],'问题二':[points[2,k]['mean_speedup'] for k in range(1,6)],'问题三（L2）':[points[3,k]['mean_speedup'] for k in range(1,6)]},'逐图平均加速比')
    figure('cycles',{'问题一':[p['total_cycles']/1e6 for p in q1],'问题二':[points[2,k]['total_cycles']/1e6 for k in range(1,6)],'问题三（L2）':[points[3,k]['total_cycles']/1e6 for k in range(1,6)]},'总执行时间（百万 cycles）')
    figure('cache_gain',{'固定问题三方案、仅切换 L2':[points[3,k]['mean_same_plan_cache_ratio'] for k in range(1,6)],'问题二方案与问题三方案比较':[comp[k] for k in range(1,6)]},'逐图同核时间比')
    coldrows=[x for folder in [cold,cold_local] for p in folder.glob('case_*/*/timing.json') for x in read(p)['rows']]
    write_json(OUT/'evidence.json',dict(points=r['points'],q1=q1,comprehensive_ratios=comp,plans=manifest,cold_rows=coldrows,full100_cold_timing=False,formal_gates='NOT_RUN',submit_ready=False))
    # Preserve the prior manuscript before synchronized replacement.
    backup=Path('output')/f'paper-before-completion-{time.strftime("%Y%m%d-%H%M%S")}.zip'
    with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
        for p in Path('论文').rglob('*.tex'):z.write(p,p.as_posix())
    chapters=Path('论文/章节');templates=OUT/'source_templates';templates.mkdir(exist_ok=True)
    for name in ['6_problem2.tex','7_problem3.tex','8_sensitivity.tex','9_evaluation.tex']:
        if not (templates/name).exists():shutil.copyfile(chapters/name,templates/name)
    p=chapters/'6_problem2.tex';src=(templates/p.name).read_text('utf-8').split(r'\subsection{继承初解')[0]
    src+=r'\input{章节/6e_current_algorithm}'+'\n'+r'\subsection{百图结果与验证}'+'\n'
    b=points[2,5];l=points[3,5]
    src+=f'问题二五核逐图平均加速比为 ${b["mean_speedup"]:.6f}$，百图总周期为 ${num(b["total_cycles"])}$，总额外搬运为 ${num(b["added_bytes"])}$ 字节。各配置保留完整官方结果与物理内存审计。历史初解作为显式输入，其生成不包含在本轮限时搜索内。\n'
    src+=table(['核数','平均加速比','总周期','额外搬运'],[[k,f'{points[2,k]["mean_speedup"]:.6f}',num(points[2,k]['total_cycles']),num(points[2,k]['added_bytes'])] for k in range(1,6)],'问题二百图汇总','tab:q2-main')+fig('speedup','三问的百图逐图平均加速比；L2 单核点沿用无 L2 单核参考','fig:q2-speed')+fig('cycles','三问百图总周期；与逐图平均加速比采用不同权重','fig:total-cycles')
    src+='算法在每个核数独立搜索，增加核心数并不保证每个图都更快。全量结果证明与给定官方仿真一致，不构成全局最优证书或未见图泛化检验。\n';text(p,src)
    p=chapters/'7_problem3.tex';src=(templates/p.name).read_text('utf-8').split(r'\subsection{固定方案消融')[0]+r'\input{章节/7e_current_algorithm}'+'\n'+r'\subsection{百图成对结果}'+'\n'
    src+=f'五核相对固定无 L2 单核参考的平均加速比为 ${l["mean_speedup"]:.6f}$，总周期为 ${num(l["total_cycles"])}$。固定最终方案只切换 L2 的逐图同核时间比为 ${l["mean_same_plan_cache_ratio"]:.6f}$；相对本轮问题二所选方案的综合时间比为 ${comp[5]:.6f}$。后者不能单独归因于缓存硬件。\n'
    src+=table(['核数','L2 平均加速比','L2 总周期','同方案硬件比','跨方案综合比'],[[k,f'{points[3,k]["mean_speedup"]:.6f}',num(points[3,k]['total_cycles']),f'{points[3,k]["mean_same_plan_cache_ratio"]:.6f}',f'{comp[k]:.6f}'] for k in range(1,6)],'问题三百图成对结果','tab:q3-main')+fig('cache_gain','固定问题三方案的 L2 效应与跨方案综合比较','fig:q3-gain')
    src+=r'\label{fig:q3-speed}'+'\n'+f'问题三五核总额外逻辑搬运为 ${num(l["added_bytes"])}$ 字节。附录的同方案无 L2 与 L2 两次评价采用同一逻辑搬运口径，不从额外搬运中扣除命中字节。命中率并不单独决定周期：FIFO 淘汰、并发冷读、双带宽竞争与数据释放的改变均会影响关键路径。\n'
    text(p,src)
    # Recompute current diagnostics; never relabel historical distributions as new.
    import numpy as np
    with Path('图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig') as f:q1rows=list(csv.DictReader(f))
    distributions={1:[float(x['speedup']) for x in q1rows if int(x['cores'])==5]}
    distributions.update({q:[matrix[q,n,5][0]['single']/matrix[q,n,5][0]['makespan'] for n in range(1,101)] for q in (2,3)})
    counts={q:sum(matrix[q,n,k][0]['makespan']>matrix[q,n,k-1][0]['makespan'] for n in range(1,101) for k in range(2,6)) for q in (2,3)}
    negative={k:sum(matrix[3,n,k][0]['makespan']>matrix[3,n,k][0]['no_l2_makespan'] for n in range(1,101)) for k in range(1,6)}
    src=r'''\section{模型检验与敏感性分析}
\subsection{逐配置账本与指标重算}
以 $\mathcal I=\{1,\ldots,100\}\times\{1,\ldots,5\}$ 为逐问结果索引，每问必须恰有500份方案，既不能缺项，也不能用同一配置重复填数。合并本机和服务器结果后，依次核对输入与源码身份、方案文件哈希、官方结果哈希、节点覆盖及核上顺序，再从官方完整记录提取周期和额外搬运；问题三还核对最终同方案无L2和L2两次的逻辑搬运相等。任何缺项、非法方案或哈希冲突均中止表格生成。

题目要求的平均与辅助总周期比分别为
\begin{equation}\label{eq:validation-vector-mean}
\overline S_k=\frac1{100}\sum_i\frac{T^0_{i,1}}{T_{i,k}},\qquad
R_k^\Sigma=\frac{\sum_iT^0_{i,1}}{\sum_iT_{i,k}}.
\end{equation}
前者给每张图等权，后者更受大周期图影响。计算百分比降幅时同样先说明参照：对单个配置为 $1-T_{i,k}/T^0_{i,1}$，总周期降幅为 $1-1/R_k^\Sigma$；二者的聚合顺序不可互换。方案搜索以每配置周期最小为主，赛题规定的平均加速比是结果摘要，不是牺牲大图完成时间来抬高小图均值的理由。
'''
    src+=table(['问题','五核平均加速比','五核总周期比','总周期下降率'],[[q,f'{(q1[4] if q==1 else points[q,5])["mean_speedup"]:.6f}',f'{single/(q1[4] if q==1 else points[q,5])["total_cycles"]:.6f}',f'{100*(1-(q1[4] if q==1 else points[q,5])["total_cycles"]/single):.4f}'+r'\%'] for q in (1,2,3)],'平均加速比和总周期口径对照','tab:metric-perspective')
    src+=r'''\subsection{五核分布与核数稳定性}
按逐图加速比排序并作线性插值，报告给定百图的经验分位数。这些统计描述本次测试集，不是对未知图分布的置信区间。均值相同也可能对应完全不同的低分位表现，后续优化应分别检查低加速图与绝对周期占比大的图。
'''
    src+=table(['问题','最小','四分位','中位数','四分之三位','最大'],[[q]+[f'{x:.4f}' for x in np.quantile(distributions[q],[0,.25,.5,.75,1])] for q in (1,2,3)],'五核逐图加速比的经验分布','tab:fivecore-quantiles')
    src+=f'本轮问题二有{counts[2]}个、问题三有{counts[3]}个相邻核数比较出现较多核反而更慢。它们说明当前有限候选池未保证核数间的嵌入保底，不证明物理最优值必然随核数增加。核心映射、子图边界与全局事件竞争共同变化，不能只由两个周期数字判断是哪一种机制导致退步。\n'
    src+=r'''\subsection{成对缓存检验与负例}
对每个最终问题三方案定义 $\delta_{i,k}=T^{L2}_i(p_{L,i,k})-T^B_i(p_{L,i,k})$。$\delta<0$ 表示同方案启用L2更快，$\delta>0$ 为反例；不能把它与问题三搜索相对另一个问题二方案的胜负混在一起。
'''
    src+=table(['核数','同方案启用 L2 后较慢的图数'],[[k,negative[k]] for k in range(1,6)],'固定最终方案的缓存负例统计','tab:cache-negative')
    src+=r'''FIFO 命中和填充分别发生在发射及完成事件，带宽改变会使后续事件重排，因此容量或带宽变化没有一般的逐方案单调保证。保留的历史机制实验中，第44图整图单核方案在L2容量0、64、128、256、512、1024、2048 KiB下分别为154407、154272、154407、154407、134726、107814、107814周期。这是同一历史方案的事后容量扫描，不是本轮新算法在各容量下重新搜索的成绩；主实验参数始终固定为题面数值。

\subsection{复用正确性、时间预算与复现范围}
生成准备复用仅作用于不可变图上的确定性函数，以完整参数指纹识别重复状态，不省略新方案的全局评价。最终所选方案重新调用原版官方评价，并比较完整结果，而非只比较一个Makespan数字；物理缓存审计还检查整个执行过程中各实例的生命周期和容量。格式合法、事件评价成功与物理容量通过是不同检查，不能互相代替。

主机墙钟耗时由图解析、初解生成、候选构造、核内准备、全局事件仿真和最后复核组成。历史种子已经在磁盘上时，590秒搜索含最终复核但不包含此前求种子的成本；图输入冷启动必须把前序阶段累计计入。两机分片运行记录主机和并发信息，禁止用整批耗时除以任务数冒充逐配置时间。具体冷启动压力结果见表\ref{tab:cold-time}。

全量覆盖证明给定输入、参数与官方语义下可复核，不等于全局最优证明。自适应候选权重使用实测耗时，相同种子在不同硬件上未必走相同轨迹；保存方案的独立重放才是对最终成绩的确定性复现。对缓存开关、候选顺序或搜索预算的独立归因，仍须保持相同初解和总时间，不能用增大计算机会后的成绩直接宣称某个组件有效。
'''
    text(chapters/'8_sensitivity.tex',src)
    p=chapters/'9_evaluation.tex';src=(templates/p.name).read_text('utf-8').split(r'\subsection{结论}')[0]
    src=src.replace('$4.159974$','$'+f'{b["mean_speedup"]:.6f}'+'$').replace('$4.240375$','$'+f'{l["mean_speedup"]:.6f}'+'$')
    src=src.replace(r'图\ref{fig:fivecore-cdf}与表\ref{tab:q3-bytes-hit}也提醒','历史分布诊断与当前搬运账本也提醒')
    src+=r'\subsection{结论}'+'\n'+f'三问分别保存了100图、1至5核的500份合法方案。五核逐图平均加速比分别为3.665903、{b["mean_speedup"]:.6f}、{l["mean_speedup"]:.6f}；问题三最终方案在同核下仅切换L2的平均时间比为{l["mean_same_plan_cache_ratio"]:.6f}。目标是降低实际完成周期，加速比用于按题目口径归纳结果；额外搬运在周期相同时进一步优化。\n'
    src+=r'\subsection{冷启动与计时边界}'+'\n'+f'另选{len(set(x["case"] for x in coldrows))}张预先指定的代表图、长依赖图及大图，从原始图依次构造三问方案，不读取历史初解。冷启动指新进程且不复用算法缓存，不清空操作系统页缓存。下表把前序初解生成累计计入；这些重新生成的初解与全量热启动证据不保证相同，因此计时压力实验不替换正文成绩。尚未完成100图全部核数的图输入端到端冷启动核验，不能声称十分钟目标全面满足。\n'
    src+=table(['算例','问题','本阶段秒数','累计秒数','完整复核'],[[x['case'],x['problem'],f'{x["standalone_stage_seconds"]:.2f}',f'{x["graph_only_cumulative_seconds"]:.2f}','通过' if x['verified'] else '未完成'] for x in coldrows],'从原始图开始的冷启动压力核验','tab:cold-time');text(p,src)
    text(chapters/'0_abstract.tex',f'''面向多计算管道和共享外存的神经网络处理器，本文在算子依赖约束下联合选择子图划分、核心映射与执行顺序，以官方仿真总完成时间为主要目标，同时间下优先减少额外数据搬运。模型按跨子图经DDR、同核驻留与跨核同步、共享只读FIFO缓存三种机制逐层扩展。

对问题一，采用无环有向图划分与多核列表调度，从完整分量、共享输入与有界局部切分生成候选，保护基础划分机会并进行关键区域联合调整。百图五核逐图平均加速比为3.665903，总周期为73170501。

对问题二，按跨核搬运完成后500周期释放建立事件约束，采用保护基础搜索的结构算法组合，并复用不变的候选生成准备。五核逐图平均加速比为{b['mean_speedup']:.6f}，总周期为{b['total_cycles']}。对问题三，加入共享FIFO状态和DDR、L2独立带宽池，在普通结构候选之外引入缓存事件邻域；五核平均加速比为{l['mean_speedup']:.6f}，总周期为{l['total_cycles']}。固定最终方案、仅切换L2时，相同核数的平均时间比为{l['mean_same_plan_cache_ratio']:.6f}，与跨方案综合比{comp[5]:.6f}分开报告。

三问均保存100图、1至5核的逐配置官方结果。结果表明，减少搬运或增加缓存命中并不保证缩短关键路径，应以完整事件仿真裁决。算法不穷举组合空间；冷启动大图压力核验与历史初解成本单列，尚不能把限时搜索结果解释为所有图端到端均在十分钟内完成，也未证明全局最优。
''')
    # Required source appendix builder, preserving custom manifest metadata.
    previous=read(Path('程序/code_manifest.json'))
    subprocess.run([sys.executable,'工具/build_code_appendix.py','--workspace','.','--output','论文/章节/A_generated_core.tex'],check=True)
    import importlib.util
    spec=importlib.util.spec_from_file_location('appendix_tool','工具/build_code_appendix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    current=read(Path('程序/code_manifest.json'));names={'q1_submit.py','q1_experimental.py','q23_submit_current.py','q23_portfolio_reuse.py','q2_timed_portfolio.py','q3_timed_combination.py','q23_selective_reuse.py'}
    for x in current['files']:x['required_in_appendix']=Path(x['path']).name in names
    current={**previous,**current};current.update(entrypoint='程序/q1_submit.py',command='python q1_submit.py GRAPH -n K --output DIR --verify-final',audit_command='python 程序/q1_submit.py GRAPH -n K --output DIR --verify-final')
    current['per_problem_entries']={'q1':'程序/q1_submit.py','q2':'程序/q23_submit_current.py --problem 2','q3':'程序/q23_submit_current.py --problem 3'}
    write_json(Path('程序/code_manifest.json'),current)
    # The machine manifest retains every dependency; paper lists actual core only.
    text(chapters/'A_generated_core.tex',m.render_latex({**current,'files':[x for x in current['files'] if x['required_in_appendix']]}))
    text(chapters/'A_code.tex',r'''\input{章节/A_generated_core}
\clearpage
\section{问题一逐用例官方结果}
加速比为固定单核时间除以本配置时间。
\input{../图表/runs/20260924-A-q1-delivery-r02/appendix_results.tex}
\clearpage
\section{问题二逐用例官方结果}
各核数均为100图，额外搬运单位为bytes。
\input{../图表/runs/20260926-A-q123-complete-delivery/q2_appendix.tex}
\clearpage
\section{问题三最终方案的同方案成对结果}
每行的无L2与L2周期来自同一最终方案的独立官方评价，两次额外逻辑搬运相同，表中合列一次；命中率为官方字节命中率。
\input{../图表/runs/20260926-A-q123-complete-delivery/q3_appendix.tex}
''')
    fm=read(Path('图表/figure_manifest.json'));key='figures';fm.setdefault(key,[])
    fm[key]=[x for x in fm[key] if not x.get('path','').startswith(OUT.as_posix()+'/')]
    for name,claim in [('speedup','逐图平均加速比'),('cycles','百图总周期'),('cache_gain','同方案硬件效应与跨方案综合比较')]:fm[key].append(dict(path=(OUT/(name+'.pdf')).as_posix(),claim=claim,source=(OUT/'evidence.json').as_posix(),reader_task='比较核数与场景',publish=True,placement='body'))
    write_json(Path('图表/figure_manifest.json'),fm)
    allresults=read(Path('图表/全部结果.json'));allresults['latest_complete_delivery']=dict(path=OUT.as_posix(),plans=1500,paired_q3=500,full100_cold_timing=False,submit_ready=False);write_json(Path('图表/全部结果.json'),allresults)
    text(OUT/'README.md','# 三问同步交付\n\n1500份标准方案；Q3最终方案500组同方案无L2/L2对照。冷启动为预先声明的压力样本，并非全量耗时认证。当前正式门禁与身份信息仍须验收。\n')
    if a.compile:
        build=ROOT/'论文/build/20260926-completion';build.mkdir(parents=True,exist_ok=True)
        exe=shutil.which('xelatex');assert exe,'XeLaTeX unavailable'
        for i in range(3):
            c=subprocess.run([exe,'-disable-installer','-interaction=nonstopmode','-halt-on-error','-no-shell-escape',f'-output-directory={build}','论文正文.tex'],cwd=ROOT/'论文',capture_output=True)
            (build/f'pass-{i}.txt').write_bytes(c.stdout+c.stderr)
            if c.returncode:raise RuntimeError(f'Compile failed; see {build}')
        shutil.copyfile(build/'论文正文.pdf',ROOT/'论文/数模论文.pdf')
        log=(build/'论文正文.log').read_text('utf-8',errors='replace')
        warnings=[line for line in log.splitlines() if any(t in line for t in ['Overfull','undefined','Missing character'])]
        write_json(OUT/'compile.json',dict(passes=3,warnings=warnings,pdf_sha256=sha(ROOT/'论文/数模论文.pdf'),visual_review='NOT_RUN'))
        for tool in ['工具/rendered_visual_audit.py','工具/pdf_layout_audit.py']:
            proc=subprocess.run([sys.executable,tool,'--workspace','.','--strict'],capture_output=True);text(OUT/(Path(tool).stem+'.log'),proc.stdout.decode('utf-8','replace')+proc.stderr.decode('utf-8','replace'))
        if warnings:raise RuntimeError('Compiled but layout/reference warnings require repair')
    print('Complete matrix/materials refreshed; formal acceptance and visual review remain separate.')

if __name__=='__main__':main()
