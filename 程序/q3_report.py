"""Aggregate only complete Q3 evidence; Chinese figures and 500-row appendix."""
import argparse,csv,json,statistics
from pathlib import Path
from q1_io import ROOT,sha,write_json


def csvout(p,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    rows=json.loads((a.run/'progress.json').read_text());rows.sort(key=lambda x:(x['case'],x['cores']))
    assert len(rows)==500 and len({(r['case'],r['cores']) for r in rows})==500
    assert json.loads((a.run/'completion.json').read_text())['complete']
    assert json.loads((a.run/'verification.json').read_text())['passed']
    a.output.mkdir(parents=True,exist_ok=False)
    single={r['case']:r['no_l2'] for r in rows if r['cores']==1}
    curve=[]
    for n in range(1,6):
        rr=[r for r in rows if r['cores']==n]
        curve.append(dict(cores=n,no_l2_speedup=statistics.mean(single[r['case']]/r['no_l2'] for r in rr),
          fixed_l2_speedup=statistics.mean(single[r['case']]/r['fixed_l2'] for r in rr),
          selected_l2_speedup=statistics.mean(single[r['case']]/r['selected_l2'] for r in rr),
          hardware_ratio=statistics.mean(r['hardware_ratio'] for r in rr),
          combined_ratio=statistics.mean(r['combined_ratio'] for r in rr),
          search_ratio=statistics.mean(r['search_ratio'] for r in rr),
          mean_fixed_hit_rate=statistics.mean(r['fixed_hit_rate'] for r in rr),
          mean_selected_hit_rate=statistics.mean(r['selected_hit_rate'] for r in rr),
          pooled_fixed_hit_rate=sum(r['fixed_hit_bytes'] for r in rr)/sum(r['fixed_hit_bytes']+r['fixed_miss_bytes'] for r in rr),
          no_l2_total_cycles=sum(r['no_l2'] for r in rr),fixed_l2_total_cycles=sum(r['fixed_l2'] for r in rr),selected_l2_total_cycles=sum(r['selected_l2'] for r in rr),
          hardware_wins=sum(r['fixed_l2']<r['no_l2'] for r in rr),hardware_ties=sum(r['fixed_l2']==r['no_l2'] for r in rr),hardware_losses=sum(r['fixed_l2']>r['no_l2'] for r in rr),
          search_wins=sum(r['selected_l2']<r['fixed_l2'] for r in rr),search_ties=sum(r['selected_l2']==r['fixed_l2'] for r in rr)))
    summary=dict(count=500,curve=curve,ratio_aggregation='arithmetic mean of per-case ratios; common no-L2 single-core denominator for speedup curves',
        hardware_losses=[{k:r[k] for k in ['case','cores','no_l2','fixed_l2','selected_l2','fixed_hit_rate']} for r in rows if r['fixed_l2']>r['no_l2']],
        combined_losses=[{k:r[k] for k in ['case','cores','no_l2','fixed_l2','selected_l2','selected_hit_rate']} for r in rows if r['selected_l2']>r['no_l2']],
        total_search_improved=sum(r['selected_l2']<r['fixed_l2'] for r in rows),
        baseline_total_added=sum(r['no_l2_added'] for r in rows),selected_total_added=sum(r['selected_l2_added'] for r in rows),
        source_sha256=sha((a.run/'progress.json').read_bytes()),formal_gate='NOT_RUN')
    write_json(a.output/'summary.json',summary);csvout(a.output/'five_point_curve.csv',curve);csvout(a.output/'pairs.csv',rows)
    tex=[r'\begin{longtable}{rrrrr}',r'\caption{问题三逐用例执行周期}\label{tab:q3-time}\\',
         r'\toprule 用例 & 核数 & 无L2 & 同方案L2 & 优化L2\\\midrule',r'\endfirsthead',
         r'\toprule 用例 & 核数 & 无L2 & 同方案L2 & 优化L2\\\midrule',r'\endhead']
    for r in rows:
        tex.append(f"{r['case']} & {r['cores']} & {r['no_l2']} & {r['fixed_l2']} & {r['selected_l2']} "+r'\\')
    tex += [r'\bottomrule',r'\end{longtable}']
    tex += [r'同方案的逻辑额外搬运量与无L2相同；无L2命中率不适用。',
            r'\begin{longtable}{rrrrrr}',r'\caption{问题三逐用例额外搬运字节与字节命中率}\label{tab:q3-traffic}\\',
            r'\toprule 用例 & 核数 & 基线额外字节 & 优化额外字节 & 同方案命中率 & 优化命中率\\\midrule',r'\endfirsthead',
            r'\toprule 用例 & 核数 & 基线额外字节 & 优化额外字节 & 同方案命中率 & 优化命中率\\\midrule',r'\endhead']
    for r in rows:
        tex.append(f"{r['case']} & {r['cores']} & {r['no_l2_added']} & {r['selected_l2_added']} & {r['fixed_hit_rate']:.4f} & {r['selected_hit_rate']:.4f} "+r'\\')
    tex += [r'\bottomrule',r'\end{longtable}']
    (a.output/'appendix_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font=font_manager.FontProperties(fname='C:/Windows/Fonts/simsun.ttc')
    plt.rcParams.update({'font.family':font.get_name(),'font.size':12,'axes.unicode_minus':False,'pdf.fonttype':42})
    n=[r['cores'] for r in curve]
    for name,ylabel,series in [
        ('speedup','平均加速比',[('no_l2_speedup','无L2：问题二方案','o','#555555'),('fixed_l2_speedup','只读L2：同一方案','s','#0072B2'),('selected_l2_speedup','只读L2：调度优化','^','#D55E00')]),
        ('cache_gain','相同核数的平均时间比',[('hardware_ratio','无L2 / 同方案L2','s','#0072B2'),('combined_ratio','无L2 / 优化L2','^','#D55E00')])]:
        fig,ax=plt.subplots(figsize=(6.2,4.2),layout='constrained')
        for k,label,marker,color in series:ax.plot(n,[r[k] for r in curve],marker=marker,color=color,label=label,linewidth=1.5)
        ax.set(xlabel='核心数',ylabel=ylabel,xticks=n);ax.grid(alpha=.18)
        ax.legend(loc='lower center',bbox_to_anchor=(.5,1.02),ncol=1,frameon=False,fontsize=12)
        for suffix in ['pdf','png']:fig.savefig(a.output/f'{name}.{suffix}',dpi=300)
        plt.close(fig)
    sensitivity=json.loads((ROOT/'图表/runs/20260924-A-q3-sensitivity-r01/rows.json').read_text())
    plt.rcParams.update({'font.size':14})
    fig,axes=plt.subplots(1,2,figsize=(9,3.5),layout='constrained')
    for n,marker,color in [(3,'o','#0072B2'),(5,'s','#D55E00')]:
        base=next(r['makespan'] for r in sensitivity if r['case']==5 and r['cores']==n and r['capacity']==1048576 and r['bandwidth']==250)
        cap=sorted([r for r in sensitivity if r['case']==5 and r['cores']==n and r['bandwidth']==250],key=lambda r:r['capacity'])
        bw=sorted([r for r in sensitivity if r['case']==5 and r['cores']==n and r['capacity']==1048576],key=lambda r:r['bandwidth'])
        axes[0].plot([r['capacity']/1048576 for r in cap],[r['makespan']/base for r in cap],marker=marker,color=color,label=f'{n}核')
        axes[1].plot([r['bandwidth'] for r in bw],[r['makespan']/base for r in bw],marker=marker,color=color,label=f'{n}核')
    axes[0].set(xlabel='L2容量（MiB）',ylabel='周期 / 固定配置周期',xticks=[0,.5,1,2])
    axes[1].set(xlabel='L2带宽（bytes/cycle）',ylabel='周期 / 固定配置周期',xticks=[60,125,250,500])
    for ax in axes:ax.grid(alpha=.18);ax.legend(frameon=False,loc='best')
    for suffix in ['pdf','png']:fig.savefig(a.output/f'sensitivity.{suffix}',dpi=300)
    plt.close(fig)
    plt.rcParams.update({'font.size':12})
    cap=json.loads((ROOT/'图表/runs/20260924-A-q3-cache-mechanism-r02/singlecore_capacity.json').read_text())
    fig,ax=plt.subplots(figsize=(6.2,3.8),layout='constrained')
    ax.plot([r['capacity']/1048576 for r in cap],[r['makespan'] for r in cap],marker='o',color='#0072B2')
    ax.set(xlabel='L2容量（MiB）',ylabel='执行时间（cycles）',xticks=[0,.25,.5,1,2]);ax.grid(alpha=.18)
    for suffix in ['pdf','png']:fig.savefig(a.output/f'singlecore_capacity.{suffix}',dpi=300)
    plt.close(fig)
    write_json(a.output/'artifact_manifest.json',{x.name:sha(x.read_bytes()) for x in a.output.iterdir() if x.is_file()})
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
