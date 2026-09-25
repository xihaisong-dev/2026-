#!/usr/bin/env python3
"""Publication plots generated only from saved input features and official results.

Outputs: 300 dpi PNG, vector SVG/PDF, and figure-specific source-data CSV files.
No simulated or invented measurements are drawn. Run with --static-only before
experiments finish. The default data files are results/dataset_features.csv,
results/results.csv (the default experiment-runner output).
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
from matplotlib.text import Text

ROOT=Path(__file__).resolve().parents[1]
COLORS={'A':'#315D85','B':'#308579','L2':'#AD6C3F','grey':'#68717D','light':'#ECF1F5'}
TYPOGRAPHY_AUDIT={}


def style():
    candidates=[Path('/usr/local/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf'),
                Path('C:/Windows/Fonts/msyh.ttc'),Path('C:/Windows/Fonts/simhei.ttf')]
    for font in candidates:
        if font.exists():
            font_manager.fontManager.addfont(str(font)); name=font_manager.FontProperties(fname=str(font)).get_name(); break
    else:
        available={f.name for f in font_manager.fontManager.ttflist}
        name=next((s for s in ['Noto Sans CJK SC','Microsoft YaHei','SimHei','Arial Unicode MS'] if s in available),'DejaVu Sans')
    plt.rcParams.update({'font.family':name,'font.size':10,'axes.labelsize':10.5,'axes.titlesize':11.5,
                         'axes.titleweight':'normal','axes.spines.top':False,'axes.spines.right':False,
                         'axes.linewidth':.75,'axes.edgecolor':'#717782','xtick.color':'#444B54','ytick.color':'#444B54',
                         'axes.labelcolor':'#202630','text.color':'#202630','axes.unicode_minus':False,
                         'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white',
                         'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','legend.frameon':False,
                         'grid.color':'#DCE1E6','grid.linewidth':.6,'grid.alpha':.75})


def save(fig, out, name, data=None):
    out.mkdir(parents=True,exist_ok=True)
    # Word inserts these figures at 15.5 cm. Use the real tight-bbox width,
    # not figsize, to raise only labels that would print below 8 pt. This
    # leaves the already legible compact method diagram unchanged.
    print_width_inches=15.5/2.54
    for _ in range(5):
        fig.canvas.draw()
        width_inches=fig.get_tightbbox(fig.canvas.get_renderer()).width+.20
        floor=8.15*width_inches/print_width_inches
        changed=False
        for item in fig.findobj(match=Text):
            if item.get_visible() and item.get_text().strip() and item.get_fontsize()<floor-.01:
                item.set_fontsize(floor);changed=True
        if not changed:break
    for suffix in ['png','svg','pdf']:
        fig.savefig(out/f'{name}.{suffix}',dpi=300,bbox_inches='tight',pad_inches=.10)
    from PIL import Image
    with Image.open(out/f'{name}.png') as picture:png_width=picture.width
    fonts=[item.get_fontsize() for item in fig.findobj(match=Text) if item.get_visible() and item.get_text().strip()]
    min_effective=min(fonts)*print_width_inches/(png_width/300) if fonts else None
    TYPOGRAPHY_AUDIT[name]={'png_width_pixels':png_width,'dpi':300,'word_width_cm':15.5,
                           'smallest_source_font_pt':min(fonts) if fonts else None,
                           'smallest_printed_font_pt':min_effective}
    if min_effective is not None and min_effective<8.0:
        raise ValueError(f'{name}: smallest printed font is only {min_effective:.2f} pt')
    plt.close(fig)
    if data is not None:data.to_csv(out/f'{name}_data.csv',index=False,encoding='utf-8-sig')
    print(name)


def grid(ax): ax.set_axisbelow(True); ax.grid(axis='y')


def method_diagram(out):
    fig,ax=plt.subplots(figsize=(8.0,5.3));ax.set(xlim=(0,10),ylim=(0,10));ax.axis('off')
    def box(x,y,w,h,text,face='#F1F4F7',edge='#9FAFBE',fontsize=10):
        p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.045,rounding_size=.09',linewidth=.9,edgecolor=edge,facecolor=face)
        ax.add_patch(p);ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fontsize,linespacing=1.5)
    def arrow(a,b,color='#7B8794',style='-|>'):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle=style,mutation_scale=11,linewidth=.9,color=color,connectionstyle='arc3'))
    box(2.2,8.85,5.6,.82,'计算图与固定硬件配置\n保留官方输入、缓存容量及总 DDR 带宽')
    box(2.2,7.45,5.6,.86,'结构分析与候选生成\n连通分量 · 双计算管道负载 · 共享输入复用')
    arrow((5,8.85),(5,8.34))
    branches=[(.15,'完整分量分配与分批','轮转 / LPT / Pipe 负载平衡',COLORS['A']),
              (3.52,'分量内切分','链收缩 / 拓扑窗口 / 通信感知列表',COLORS['B']),
              (6.89,'同核顺序调整','共享输入局部复用（场景 B）',COLORS['L2'])]
    for x,title,desc,c in branches:
        box(x,5.75,2.96,1.03,title+'\n'+desc,edge=c,fontsize=9)
        arrow((5,7.45),(x+1.48,6.81))
    ax.text(5,5.41,'大分量影响负载均衡时启用细分候选；重复方案去重',ha='center',fontsize=9,color=COLORS['grey'])
    box(1.2,3.72,7.6,1.10,'官方评估与合法性筛选\n构造 Task → 核内排程与换入换出 → 共享 DDR / Cache 事件模拟',face='#EDF4F2',edge=COLORS['B'],fontsize=10)
    for x,_,_,_ in branches:arrow((x+1.48,5.73),(x+1.48,4.86))
    box(2.2,2.14,5.6,.89,'逐实例、逐核数选优\n先比较 Makespan，再比较额外搬运量',edge=COLORS['A'])
    arrow((5,3.72),(5,3.07))
    endings=[(.15,'问题一：场景 A','跨子图数据均经 DDR',COLORS['A']),
             (3.52,'问题二：场景 B','同核复用，跨核同步',COLORS['B']),
             (6.89,'问题三：只读 L2','同方案成对对照',COLORS['L2'])]
    for x,title,desc,c in endings:
        box(x,.25,2.96,1.05,title+'\n'+desc,edge=c,fontsize=9.5);arrow((5,2.12),(x+1.48,1.34))
    save(fig,out,'fig01_method')


def dataset_figure(features,out):
    f=features.copy(); f['cube_fraction']=f.cube_cycles/f.compute_cycles.replace(0,np.nan)
    fig,axs=plt.subplots(1,2,figsize=(8.2,3.45),layout='constrained')
    ax=axs[0]
    sc=ax.scatter(f.n_compute_ops,f.original_ddr_bytes/2**20,c=f.cube_fraction,cmap='viridis',s=30,alpha=.84,linewidth=.35,edgecolors='white',vmin=0,vmax=1)
    ax.set(xscale='log',yscale='log',xlabel='计算操作数',ylabel='原始 DDR 搬运量 / MiB',title='(a) 图规模与原始搬运需求')
    ax.grid(alpha=.45); cb=fig.colorbar(sc,ax=ax,pad=.02,fraction=.05);cb.set_label('Cube 计算周期占比',fontsize=9)
    ax=axs[1]; ax.scatter(f.n_components,f.work_over_critical_path,s=30,c=COLORS['B'],alpha=.76,linewidth=.35,edgecolors='white')
    ax.set(xscale='log',yscale='log',xlabel='计算 DAG 的弱连通分量数',ylabel='总计算周期 / 计算关键路径周期',title='(b) 依赖结构与计算并行潜力');ax.grid(alpha=.45)
    save(fig,out,'fig02_dataset',f[['case','n_compute_ops','original_ddr_bytes','cube_fraction','n_components','work_over_critical_path']])


def speedup_summary(data):
    return data.groupby(['problem','cores']).speedup.agg(mean='mean',median='median',q25=lambda x:x.quantile(.25),q75=lambda x:x.quantile(.75),min='min',max='max',count='count').reset_index()


def speedup_figures(data,out):
    selected=data[data.problem.isin([1,2])].copy()
    if selected.empty:return
    summary=speedup_summary(selected)
    fig,axs=plt.subplots(1,2,figsize=(8.0,3.3),sharey=True,layout='constrained')
    for ax,problem,label,c in zip(axs,[1,2],['(a) 问题一：场景 A','(b) 问题二：场景 B'],[COLORS['A'],COLORS['B']]):
        sub=summary[summary.problem==problem].sort_values('cores')
        ax.plot([1,5],[1,5],ls='--',c='#ACB2B9',lw=1,label='线性加速参考')
        ax.fill_between(sub.cores,sub.q25,sub.q75,color=c,alpha=.12,label='实例四分位范围')
        ax.plot(sub.cores,sub['mean'],'o-',c=c,lw=1.8,ms=5,label='实例加速比的算术平均')
        for row in sub.itertuples():ax.annotate(f'{row.mean:.2f}',(row.cores,row.mean),xytext=(0,7),textcoords='offset points',ha='center',fontsize=9,color=c)
        ax.set(title=label,xlabel='核心数',xticks=range(1,6),xlim=(.83,5.17));grid(ax)
        ax.legend(loc='upper left',fontsize=8)
    axs[0].set_ylabel('相对于整图单核的加速比')
    save(fig,out,'fig03_speedup',summary)
    # Empirical distribution retains heterogeneity hidden by the mean.
    fig,axs=plt.subplots(1,2,figsize=(8,3.15),layout='constrained')
    five=selected[selected.cores==5]
    for problem,label,c in [(1,'场景 A',COLORS['A']),(2,'场景 B',COLORS['B'])]:
        s=np.sort(five.loc[five.problem==problem,'speedup'].dropna())
        if len(s):axs[0].step(s,np.arange(1,len(s)+1)/len(s),where='post',label=label,color=c,lw=1.8)
    axs[0].axvline(1,color='#9A9FA7',ls=':',lw=1);axs[0].set(xlabel='5 核加速比',ylabel='累计实例比例',title='(a) 实例收益的经验分布',ylim=(0,1.03));axs[0].legend();grid(axs[0])
    paired=five.pivot(index='case',columns='problem',values='makespan').dropna()
    if len(paired):
        paired['ratio_A_over_B']=paired[1]/paired[2]
        ratio=paired.ratio_A_over_B.sort_values();x=np.arange(len(ratio))
        axs[1].bar(x,ratio-1,color=np.where(ratio>=1,COLORS['B'],COLORS['L2']),width=1)
        axs[1].axhline(0,c='#808893',lw=.8);axs[1].set(xlabel='按场景 B 相对收益排序的实例',ylabel='场景 A / 场景 B − 1',title='(b) 硬件场景变化后的配对收益');grid(axs[1])
    save(fig,out,'fig04_case_distribution',five)


def cache_figures(pairs,out):
    required={'case','cores','uncached_makespan','cached_makespan','cache_hit_rate'}
    if not required.issubset(pairs):raise ValueError('cache_pairs missing '+str(required-set(pairs)))
    p=pairs.copy();p['relative_speedup']=p.uncached_makespan/p.cached_makespan
    if 'baseline_makespan' in p:
        p['uncached_speedup']=p.baseline_makespan/p.uncached_makespan
        p['cached_speedup']=p.baseline_makespan/p.cached_makespan
    g=p.groupby('cores').agg(uncached_mean=('uncached_makespan','mean'),cached_mean=('cached_makespan','mean'),relative_mean=('relative_speedup','mean'),relative_median=('relative_speedup','median'),hit_mean=('cache_hit_rate','mean'),count=('case','count')).reset_index()
    if 'baseline_makespan' in p:
        speeds=p.groupby('cores')[['uncached_speedup','cached_speedup']].mean().reset_index()
        g=g.merge(speeds,on='cores',validate='one_to_one')
    fig,axs=plt.subplots(1,2,figsize=(8.0,3.2),layout='constrained')
    a=axs[0]
    yu=g.uncached_speedup if 'uncached_speedup' in g else g.uncached_mean/1000
    yc=g.cached_speedup if 'cached_speedup' in g else g.cached_mean/1000
    ylabel='相对于整图单核的平均加速比' if 'uncached_speedup' in g else '平均 Makespan / 千周期'
    a.plot(g.cores,yu,'o-',c=COLORS['B'],label='同一方案：关闭 L2',ms=5,lw=1.7)
    a.plot(g.cores,yc,'s--',c=COLORS['L2'],label='同一方案：只读 L2',ms=4.5,lw=1.7)
    a.set(xlabel='核心数',ylabel=ylabel,xticks=range(1,6),title='(a) 固定方案的缓存配置对照');grid(a);a.legend(fontsize=9)
    a=axs[1];a.plot(g.cores,g.relative_mean,'o-',c=COLORS['L2'],lw=1.8,ms=5)
    for r in g.itertuples():a.annotate(f'{r.relative_mean:.3f}',(r.cores,r.relative_mean),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
    a.axhline(1,c='#9299A2',lw=.8,ls='--');a.set(xlabel='核心数',ylabel='无 L2 / 只读 L2 的平均加速比',xticks=range(1,6),title='(b) 实例相对加速比的算术平均');grid(a);a.margins(y=.30)
    save(fig,out,'fig05_cache',g)
    fig,axs=plt.subplots(1,2,figsize=(8,3.15),layout='constrained')
    x=p[p.cores==p.cores.max()].copy()
    axs[0].scatter(x.cache_hit_rate*100,x.relative_speedup,s=29,alpha=.78,c=COLORS['L2'],edgecolors='white',linewidth=.4)
    axs[0].axhline(1,c='#9299A2',lw=.8,ls='--');axs[0].set(xlabel='Cache 字节命中率 / %',ylabel='无 L2 / 只读 L2',title=f'(a) {int(p.cores.max())} 核命中率与实际收益');grid(axs[0])
    cols=['cores','cache_hit_rate'];data=[p.loc[p.cores==k,'cache_hit_rate'].dropna().to_numpy()*100 for k in sorted(p.cores.unique())]
    bx=axs[1].boxplot(data,tick_labels=sorted(p.cores.unique()),patch_artist=True,widths=.48,showfliers=True,flierprops={'marker':'.','markersize':3,'markerfacecolor':COLORS['L2'],'markeredgecolor':COLORS['L2']},medianprops={'color':COLORS['L2'],'linewidth':1.5})
    for b in bx['boxes']:b.set_facecolor('#F0E1D6');b.set_edgecolor(COLORS['L2'])
    for item in bx['whiskers']+bx['caps']:item.set_color(COLORS['L2'])
    axs[1].set(xlabel='核心数',ylabel='Cache 字节命中率 / %',title='(b) 命中率的实例间差异');grid(axs[1])
    save(fig,out,'fig07_cache_mechanism',p)


def traffic_figure(data,out):
    d=data[(data.cores==5)&data.problem.isin([1,2])].copy()
    if d.empty:return
    fig,axs=plt.subplots(1,2,figsize=(8,3.2),layout='constrained')
    for problem,label,c in [(1,'场景 A',COLORS['A']),(2,'场景 B',COLORS['B'])]:
        s=d[d.problem==problem]
        axs[0].scatter(s.added_copy_bytes/2**20,s.speedup,c=c,label=label,s=25,alpha=.67,edgecolors='white',linewidth=.35)
    axs[0].set(xlabel='总额外数据搬运量 / MiB',ylabel='5 核加速比',title='(a) 额外搬运与并行收益');axs[0].set_xscale('symlog',linthresh=.01);axs[0].legend(fontsize=9);grid(axs[0])
    g=d.groupby('problem')[['partition_added_copy_bytes','spill_added_copy_bytes']].mean()/2**20
    axs[1].bar([0,1],g.partition_added_copy_bytes.reindex([1,2]),width=.5,color='#7893AE',label='切分及输入重复读取')
    axs[1].bar([0,1],g.spill_added_copy_bytes.reindex([1,2]),bottom=g.partition_added_copy_bytes.reindex([1,2]),width=.5,color='#D2AA87',label='缓存换入 / 换出')
    axs[1].set(xticks=[0,1],xticklabels=['场景 A','场景 B'],ylabel='平均额外数据搬运量 / MiB',title='(b) 额外搬运的来源')
    max_bar=float(g.sum(axis=1).max())
    axs[1].set_ylim(0,max_bar*1.36 if max_bar>0 else 1)
    axs[1].legend(fontsize=8.5,loc='upper right');grid(axs[1])
    save(fig,out,'fig06_movement',d)


def trace_figure(tracepath,out):
    opener=gzip.open if tracepath.suffix=='.gz' else open
    with opener(tracepath,'rt',encoding='utf-8') as f:t=json.load(f)
    if 'per_core_timeline' not in t:return
    colors={'PIPE_M':COLORS['A'],'PIPE_V':COLORS['B'],'PIPE_MTE2':'#C5955D','PIPE_MTE3':'#9D84A7'}
    cores=t['per_core_timeline'];n=len(cores)
    fig,ax=plt.subplots(figsize=(8, max(2.7,n*.72)),layout='constrained'); rows=[]
    pipe_order=['PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3']
    for i,core in enumerate(cores):
        for j,pipe in enumerate(pipe_order):
            bars=[]
            for op in core.get('ops',[]):
                if op.get('pipe')!=pipe:continue
                start,end=op['start'],op['end'];bars.append((start/1000,(end-start)/1000));rows.append(dict(core=core['core_id'],pipe=pipe,op_id=op['op_id'],start=start,end=end))
            if bars:ax.broken_barh(bars,(i*5+j,.68),facecolors=colors[pipe],edgecolors='none',rasterized=False)
    ax.set(yticks=[i*5+1.7 for i in range(n)],yticklabels=[f'核心 {c["core_id"]}' for c in cores],xlabel='时间 / 千周期',xlim=(0,t['makespan']/1000),title=f'{tracepath.name.split(".")[0]}：官方模拟的四管道时间线')
    ax.invert_yaxis();ax.grid(axis='x');ax.legend(handles=[Patch(facecolor=colors[k],label=l) for k,l in zip(pipe_order,['Cube','Vector','MTE2（搬入）','MTE3（搬出）'])],ncol=4,fontsize=8,loc='lower center',bbox_to_anchor=(.5,1.14))
    save(fig,out,'fig08_gantt',pd.DataFrame(rows))


def candidate_figure(selected, candidates, out):
    """Portfolio gain against a true paired baseline; not a removal ablation."""
    d=selected[selected.problem.isin([1,2]) & (selected.cores>1)].copy()
    c=candidates[candidates.method=='component_round_robin'].copy()
    if 'status' in c: c=c[c.status=='ok']
    c=c[['case','problem','cores','makespan']].rename(columns={'makespan':'round_robin_makespan'})
    z=d.merge(c,on=['case','problem','cores'],validate='one_to_one')
    if z.empty:return
    z['gain_vs_round_robin']=z.round_robin_makespan/z.makespan
    fig,axs=plt.subplots(1,2,figsize=(8,4.0),layout='constrained')
    for problem,label,color in [(1,'场景 A',COLORS['A']),(2,'场景 B',COLORS['B'])]:
        g=z[z.problem==problem].groupby('cores').gain_vs_round_robin.mean()
        axs[0].plot(g.index,g.values,'o-',color=color,label=label,ms=4.5,lw=1.8)
    axs[0].axhline(1,color='#9A9FA7',ls='--',lw=.9)
    axs[0].set(xlabel='核心数',ylabel='轮转 / 最终方案\n平均加速比',xticks=range(2,6),title='(a) 官方模拟选优的组合收益')
    axs[0].legend(fontsize=9);grid(axs[0])
    def family(m):
        if m=='component_round_robin':return '轮转分核'
        if m=='component_lpt':return 'LPT 分核'
        if m=='component_pipe_balance':return 'Pipe 负载平衡'
        if m=='component_batches':return '完整分量分批'
        if m=='component_reuse_order':return '输入复用顺序'
        if m.startswith('chain'):return '链切分'
        if m.startswith('window'):return '窗口切分'
        return '整图回退'
    five=d[d.cores==5].copy();five['candidate_family']=five.method.map(family)
    table=pd.crosstab(five.problem,five.candidate_family).reindex([1,2],fill_value=0)
    palette=['#527797','#80A5BB','#378A7B','#91BFAF','#C28B5B','#D9B99D','#B5A6BD']
    bottom=np.zeros(2)
    for j,name in enumerate(table.columns):
        count=table[name].to_numpy();axs[1].bar([0,1],count,bottom=bottom,width=.52,color=palette[j%len(palette)],label=name)
        for k,v in enumerate(count):
            if v>=8:axs[1].text(k,bottom[k]+v/2,str(v),ha='center',va='center',fontsize=9,color='white' if j in [0,2] else '#23313A')
        bottom+=count
    axs[1].set(xticks=[0,1],xticklabels=['场景 A','场景 B'],ylabel='入选实例数',title='(b) 5 核最终方案的候选来源')
    axs[1].legend(fontsize=9,loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2);grid(axs[1])
    save(fig,out,'fig09_candidate_gain',z)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=ROOT/'results'/'results.csv')
    p.add_argument('--cache-pairs',type=Path,default=ROOT/'results'/'cache_pairs.csv')
    p.add_argument('--features',type=Path,default=ROOT/'results'/'dataset_features.csv')
    p.add_argument('--candidates',type=Path,default=ROOT/'results'/'candidates.csv')
    p.add_argument('--output-dir',type=Path,default=ROOT/'figures')
    p.add_argument('--trace',type=Path);p.add_argument('--static-only',action='store_true')
    a=p.parse_args();style();method_diagram(a.output_dir)
    if a.features.exists():dataset_figure(pd.read_csv(a.features),a.output_dir)
    if not a.static_only:
        if a.results.exists():
            d=pd.read_csv(a.results);speedup_figures(d,a.output_dir);traffic_figure(d,a.output_dir)
        else: print(f'No saved experiment results: {a.results}. Result plots skipped.')
        if a.cache_pairs.exists():
            cache_figures(pd.read_csv(a.cache_pairs),a.output_dir)
        elif a.results.exists() and 'cache_speedup_vs_same_plan' in d:
            cp=d[d.problem==3].copy()
            if len(cp):
                cp['cached_makespan']=cp['makespan']
                cp['uncached_makespan']=cp['makespan']*cp['cache_speedup_vs_same_plan']
                cache_figures(cp,a.output_dir)
        if a.results.exists() and a.candidates.exists():candidate_figure(d,pd.read_csv(a.candidates),a.output_dir)
        if a.trace:trace_figure(a.trace,a.output_dir)
    (a.output_dir/'typography_audit.json').write_text(json.dumps(TYPOGRAPHY_AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
