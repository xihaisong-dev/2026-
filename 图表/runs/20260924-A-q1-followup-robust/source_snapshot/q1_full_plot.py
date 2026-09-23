"""Publish arithmetic per-case mean speedup, never a ratio of summed times."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis',type=Path,required=True)
    args=ap.parse_args()
    p=args.analysis/'summary.json';d=json.loads(p.read_text(encoding='utf-8'))
    assert d['completed'] and d['single_baselines']==100 and d['solver_runs']==800
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(6.6,4.4),layout='constrained')
    for config,label,color,marker in [('shared_region','Baseline','#376A9B','o'),('shared_resource','Resource-aware initial partition','#CA702B','s')]:
        y=[d['by_core'][config][str(k)]['mean_speedup'] for k in [1,2,3,4,5]]
        ax.plot([1,2,3,4,5],y,marker=marker,color=color,label=label,linewidth=1.8,markersize=5)
    ax.set(xlabel='Number of AI cores',ylabel='Mean speedup across 100 cases',xticks=[1,2,3,4,5])
    ax.grid(axis='y',alpha=.2);ax.legend(loc='best',frameon=False,fontsize=9)
    for ext in ['png','pdf','svg']:fig.savefig(args.analysis/f'mean_speedup.{ext}',dpi=180)
    plt.close(fig)
    with (args.analysis/'all_case_results.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    base={r['case']:float(r['speedup']) for r in rows if r['cores']=='5' and r['config']=='shared_region'}
    new={r['case']:float(r['speedup']) for r in rows if r['cores']=='5' and r['config']=='shared_resource'}
    cases=sorted(base,key=lambda c:(base[c],c))[:15]
    fig,ax=plt.subplots(figsize=(7,5.6),layout='constrained')
    for i,c in enumerate(cases):ax.plot([base[c],new[c]],[i,i],color='#BBBBBB',linewidth=1)
    ax.scatter([base[c] for c in cases],range(len(cases)),color='#376A9B',label='Baseline',s=23)
    ax.scatter([new[c] for c in cases],range(len(cases)),color='#CA702B',label='Resource-aware initial partition',marker='x',s=28)
    ax.set(yticks=list(range(len(cases))),yticklabels=cases,xlabel='Five-core speedup (single-case ratio)')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.2);ax.legend(frameon=False,fontsize=9)
    for ext in ['png','pdf']:fig.savefig(args.analysis/f'lowest_speedup_cases.{ext}',dpi=180)
    plt.close(fig)
    (args.analysis/'figure_provenance.json').write_text(json.dumps({'source_summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'plot_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'matplotlib':matplotlib.__version__,'font':'DejaVu Sans','scope':'development all-case comparison, seed 0',
        'statistic':'mean_i(T_single_i/T_multi_i)','not_claimed':'low speedup does not prove avoidable algorithmic loss'},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
