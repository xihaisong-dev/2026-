"""Three questions, five core counts, one verified per-case reference."""
import csv,json,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'图表/runs/20260924-A-q123-comparison-r01'
def read(path):
    with (ROOT/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    sources=['图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv',
        '图表/runs/20260924-A-q2-delivery-r07/selected_500_rows.csv',
        '图表/runs/20260924-A-q3-delivery-r03/pairs.csv']
    q1,q2,q3=map(read,sources)
    assert all(len(x)==500 for x in [q1,q2,q3])
    def cid(r):return int(r['case'].replace('case_',''))
    base={cid(r):int(r['makespan']) for r in q1 if int(r['cores'])==1}
    assert len(base)==100
    assert base=={cid(r):int(r['makespan']) for r in q2 if int(r['cores'])==1}
    assert base=={cid(r):int(r['no_l2']) for r in q3 if int(r['cores'])==1}
    curves=[]
    for n in range(1,6):
        row={'cores':n}
        for name,rs,field in [('q1',q1,'makespan'),('q2',q2,'makespan'),('q3',q3,'selected_l2')]:
            selected=[r for r in rs if int(r['cores'])==n]
            assert len(selected)==100 and {cid(r) for r in selected}==set(base)
            row[name]=statistics.mean(base[cid(r)]/int(r[field]) for r in selected)
        curves.append(row)
    OUT.mkdir(parents=True,exist_ok=False)
    data=dict(curves=curves,aggregation='mean of 100 per-case speedup ratios',
        common_reference='Q1 fixed single-core = Q2 no-L2 single-core, verified all 100 cases',
        versions={'q1':'delivery-r02','q2':'delivery-r07','q3':'frozen full-r02, exported delivery-r03'},
        note='Q3 local r01-r05 experiments excluded; original 500-case baseline retained.',
        sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    (OUT/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (OUT/'five_points.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(curves[0]));w.writeheader();w.writerows(curves)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':12,'axes.unicode_minus':False,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(7.4,4.8),layout='constrained')
    for k,label,color,marker,ls in [('q1','问题一','#376795','s','-'),('q2','问题二','#D07C32','o','--'),('q3','问题三（冻结500组）','#258579','^','-')]:
        ax.plot([r['cores'] for r in curves],[r[k] for r in curves],label=label,color=color,marker=marker,linestyle=ls,linewidth=1.8,markersize=7,markerfacecolor='white',markeredgewidth=1.6)
    ax.set(xlabel='核心数',ylabel='平均加速比（统一无L2单核参照）',xticks=range(1,6),xlim=(.8,5.25),ylim=(.8,4.55))
    ax.grid(axis='y',alpha=.20);ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='upper left',frameon=False)
    for ext in ['png','pdf']:fig.savefig(OUT/f'five_point_comparison.{ext}',dpi=300)
    plt.close(fig)
    print(json.dumps(data,ensure_ascii=False))
if __name__=='__main__':main()
