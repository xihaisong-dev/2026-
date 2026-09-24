"""Render immutable Q1 delivery aggregates; plotting only requires matplotlib."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'图表/runs/20260924-A-q1-delivery-r02/aggregate.json'
data=json.loads(source.read_text(encoding='utf-8'))
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei'],'axes.unicode_minus':False,'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
def save(fig,name):
    fig.tight_layout()
    for ext in ['pdf','png']:fig.savefig(ROOT/'图表'/f'{name}.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4.5))
for field,label,marker,color,style in [('previous_mean_speedup','上一轮全量方案','s','#777777','--'),('mean_speedup','当前方案','o','#0072B2','-')]:
    ax.plot([r['cores'] for r in data],[r[field] for r in data],label=label,marker=marker,color=color,linestyle=style,linewidth=1.6)
ax.set(xlabel='核心数',ylabel='逐图加速比的算术平均（倍）',xticks=range(1,6),ylim=(0.9,4.05));ax.legend(frameon=False);ax.grid(axis='y',alpha=.2)
save(fig,'fig_q1_r02_mean_speedup')
fig,ax=plt.subplots(figsize=(7,4.5));xs=list(range(4));width=.32
for offset,field,label,color,hatch in [(-width/2,'previous_total_cycles','上一轮全量方案','#bbbbbb',''),(width/2,'total_cycles','当前方案','#56B4E9','..')]:
    ax.bar([x+offset for x in xs],[r[field]/1e6 for r in data[1:]],width=width,label=label,color=color,hatch=hatch,edgecolor='#444444',linewidth=.5)
ax.set(xlabel='核心数',ylabel='100图 Makespan 合计（百万 cycles）',xticks=xs,xticklabels=[2,3,4,5],ylim=(0,205));ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
save(fig,'fig_q1_r02_total_cycles')
manifest=ROOT/'图表/figure_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'version':1,'figures':[]}
for name,claim in [('mean_speedup','按赛题规定比较100图的逐图加速比算术平均。'),('total_cycles','同一100图当前方案2～5核总周期低于自身上一轮；此指标不替代规定平均加速比。')]:
    m['figures'].append(dict(path=f'图表/fig_q1_r02_{name}.pdf',claim=claim,source=source.relative_to(ROOT).as_posix(),reader_task='比较各核配置下自身前后方案',publish=True,placement='body'))
manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'图表/图表引用.tex').write_text(r'''% Q1 r02: insert at full linewidth (source labels 12 pt).
\begin{figure}[htbp]
\centering\includegraphics[width=\linewidth]{图表/fig_q1_r02_mean_speedup.pdf}
\caption{固定单核基准下100图逐图加速比的算术平均。}\label{fig:q1-r02-speedup}
\end{figure}
\begin{figure}[htbp]
\centering\includegraphics[width=\linewidth]{图表/fig_q1_r02_total_cycles.pdf}
\caption{同一100图不同核数的总执行周期；总周期比不等于平均加速比。}\label{fig:q1-r02-cycles}
\end{figure}
''',encoding='utf-8')
