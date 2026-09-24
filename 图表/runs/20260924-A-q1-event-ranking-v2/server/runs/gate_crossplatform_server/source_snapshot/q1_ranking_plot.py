"""Plot verified full100 mean speedups (optional matplotlib dependency)."""
import argparse,json,hashlib
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--font',type=Path);args=ap.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname=str(args.font)) if args.font else FontProperties(family='sans-serif')
    p=args.analysis/'summary.json';s=json.loads(p.read_text(encoding='utf8'));assert s['all_checks_passed']
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':11,'pdf.fonttype':42,'svg.fonttype':'path'})
    fig,ax=plt.subplots(figsize=(8,5.2),layout='constrained')
    for field,label,color,marker in [('baseline_mean_speedup','原基线','#64748b','o'),('mean_speedup','冻结新方案','#087f8c','s'),('external_mean_speedup','参考工程','#d97706','^')]:
        y=[1]+[s['full_by_core'][str(k)][field] for k in range(2,6)]
        ax.plot(range(1,6),y,label=label,color=color,marker=marker,linewidth=2)
    ax.set_xticks(range(1,6));ax.set_xlabel('核心数',fontproperties=font);ax.set_ylabel('逐用例平均加速比',fontproperties=font)
    ax.set_title('问题一：100个用例的平均加速比',fontproperties=font,pad=12)
    ax.grid(axis='y',alpha=.2);ax.legend(prop=font,frameon=False,loc='upper left');ax.set_ylim(bottom=.9)
    fig.savefig(args.analysis/'full100_speedup.png',dpi=180);fig.savefig(args.analysis/'full100_speedup.pdf');plt.close(fig)
    data={'definition':'mean over all100 cases of fixed single-core makespan / multicore makespan','source_summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'matplotlib_version':matplotlib.__version__,'formal_default_changed':False}
    (args.analysis/'figure_provenance.json').write_bytes(json.dumps(data,ensure_ascii=False,indent=2).encode())
if __name__=='__main__':main()
