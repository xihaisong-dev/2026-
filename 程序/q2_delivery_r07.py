"""Export the adopted r07 computational submission from frozen full100 evidence."""
import csv,json,shutil
from q1_io import ROOT,PROCESSED,sha,write_json
from q2_evaluator import load
from q2_full_r07_campaign import OUT as RUN,read

OUT=ROOT/'图表/runs/20260924-A-q2-delivery-r07'

def table(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    s=read(RUN/'summary.json');checks=read(RUN/'final_checks.json')
    assert s['checks']['r07_configurations']==400 and s['checks']['global_capacity_pass']==400
    assert checks['conditional_prediction_full_plan_and_cycles_match']==400
    assert not OUT.exists();OUT.mkdir(parents=True);load()
    from singlecore_evaluate import build_singlecore_plan
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    rows=[];wide=[];plans=[]
    for i in range(1,101):
        raw=read(PROCESSED/f'data/case_{i:03}.json');case=RUN/f'cases/case_{i:03}';single=read(case/'single.json');values=dict(case=i)
        for k in range(1,6):
            if k==1:
                plan=build_singlecore_plan(raw);row=dict(case=i,cores=k,makespan=single['makespan'],added_copy_bytes=single['added_copy_bytes'],speedup=1.,search_seconds=0.,role='prescribed_single_reference')
            else:
                folder=case/f'{k}/fast';r=read(folder/'row.json');plan=read(folder/'plan.json')
                row=dict(case=i,cores=k,makespan=r['makespan'],added_copy_bytes=r['bytes'],speedup=r['speedup'],search_seconds=r['solve_seconds'],role='r07_reserve_fast')
            assert set(plan)=={'node_to_subgraph','core_schedules'} and len(plan['core_schedules'])==k
            validate_task_order(derive_multicore_plan(raw,plan))
            dest=OUT/f'solutions/{k}cores/case_{i:03}_multicore_res.json';dest.parent.mkdir(parents=True,exist_ok=True);write_json(dest,plan)
            plans.append(dict(case=i,cores=k,path=dest.relative_to(ROOT).as_posix(),sha256=sha(dest.read_bytes())))
            rows.append(row);values[f'T{k}']=row['makespan'];values[f'B{k}']=row['added_copy_bytes']
        wide.append(values)
    table(OUT/'selected_500_rows.csv',rows);table(OUT/'appendix_100_cases.csv',wide)
    curves=[dict(cores=k,mean_speedup=s['curves']['r07'][str(k)],r05=s['curves']['r05'][str(k)]) for k in range(1,6)]
    table(OUT/'five_point_curve.csv',curves)
    tex=[r'\begin{longtable}{rrrrr}',r'\caption{问题二逐例执行周期与额外搬运量}\label{tab:q2-r07-appendix}\\',r'\toprule',r'算例 & 核数 & 执行周期 & 额外搬运（字节） & 加速比 \\',r'\midrule\endfirsthead',r'\toprule',r'算例 & 核数 & 执行周期 & 额外搬运（字节） & 加速比 \\',r'\midrule\endhead']
    tex += [f"{r['case']} & {r['cores']} & {r['makespan']} & {r['added_copy_bytes']} & {r['speedup']:.6f}"+r' \\' for r in rows]
    tex += [r'\bottomrule',r'\end{longtable}'];(OUT/'appendix_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc',size=14)
    plt.rcParams.update({'font.size':14,'pdf.fonttype':42,'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(6,3.9),layout='constrained')
    ax.plot(range(1,6),[x['mean_speedup'] for x in curves],marker='o',color='#176b95',linewidth=1.7,markersize=5)
    ax.set_xticks(range(1,6));ax.set_xlabel('核心数量',fontproperties=font);ax.set_ylabel('平均加速比',fontproperties=font)
    ax.set_ylim(.8,4.45);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
    for ext in ['pdf','png']:fig.savefig(OUT/f'five_point_curve.{ext}',dpi=300)
    plt.close(fig)
    (OUT/'figure.tex').write_text(r'''\begin{figure}[!htbp]
\centering
\includegraphics[width=0.72\linewidth,height=0.70\textheight,keepaspectratio]{five_point_curve.pdf}
\caption{场景B下100个算例的平均加速比，按规定单核基准与各核执行周期之比逐例取算术平均。}
\label{fig:q2-r07-speedup}
\end{figure}
''',encoding='utf-8')
    (OUT/'preview.tex').write_text(r'''\documentclass[UTF8,a4paper,12pt]{ctexart}
\usepackage[left=22.5mm,right=22.5mm,top=30mm,bottom=18mm]{geometry}
\usepackage{graphicx,longtable,booktabs}
\begin{document}
\section*{问题二计算交付预览}
本文件用于核对五点图及逐例附录排版，不是完整参赛论文。
\input{figure.tex}
\clearpage
\input{appendix_table.tex}
\end{document}
''',encoding='utf-8')
    write_json(OUT/'adoption.json',dict(problem=2,algorithm='r07_reserve_fast',entry='程序/q2_current_submit.py',decision='User selected r07 for submission; r05 retained as frozen baseline; r08 not adopted.',
        fixed_budget_B=12,seed=0,curves=s['curves']['r07'],summary_sha256=sha((RUN/'summary.json').read_bytes()),checks_sha256=sha((RUN/'final_checks.json').read_bytes()),
        formal_manuscript_acceptance=False,plans=plans))
    print(OUT)

if __name__=='__main__':main()
