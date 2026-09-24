"""Build full100 tables and review-ready figures only from completed evidence."""
import csv, gzip, json, shutil, statistics
from q1_io import ROOT, sha, write_json
from q2_full_campaign import OUT, read


def table(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    s=read(OUT/'summary.json');audit=read(OUT/'full_audit.json')
    assert audit['results']==800 and audit['selected_global_residency_checks']==400
    d=OUT/'delivery';assert not d.exists();d.mkdir()
    arm=s['selected_global_algorithm'];rows=[];plans=[];wide=[]
    for i in range(1,101):
        case=OUT/f'cases/case_{i:03}'
        with gzip.open(case/'fixed_single.json.gz','rt',encoding='utf-8') as f:r=json.load(f)
        values=dict(case=i)
        for k in range(1,6):
            if k==1:
                row=dict(case=i,cores=1,makespan=r['makespan'],added_copy_bytes=r['data_movement_bytes']['added_copy_bytes'],speedup=1.,search_seconds=0.,role='prescribed_reference')
            else:
                folder=case/f'{k}/{arm}';a=read(folder/'row.json')
                row=dict(case=i,cores=k,makespan=a['makespan'],added_copy_bytes=a['bytes'],speedup=a['speedup'],search_seconds=a['solve_seconds'],role=arm)
                source=folder/f'case_{i:03}_multicore_res.json';dest=d/f'solutions/{k}cores/{source.name}'
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
                assert dest.read_bytes()==source.read_bytes()
                plans.append(dict(path=dest.relative_to(ROOT).as_posix(),source=source.relative_to(ROOT).as_posix(),sha256=sha(dest.read_bytes())))
            rows.append(row);values[f'T{k}']=row['makespan'];values[f'B{k}']=row['added_copy_bytes']
        wide.append(values)
    table(d/'selected_500_rows.csv',rows);table(d/'appendix_100_cases.csv',wide)
    curves=[dict(cores=k,legacy=s['curves']['legacy'][str(k)],routed=s['curves']['routed'][str(k)],selected=s['curves'][arm][str(k)]) for k in range(1,6)]
    table(d/'five_point_curve.csv',curves)
    tex=['% Requires longtable and booktabs. T: cycles; B: added bytes.',r'\begin{longtable}{rrrrr}',r'\caption{问题二逐例执行周期与额外搬运量}\label{tab:q2-full-appendix}\\',r'\toprule',r'算例 & 核数 & 执行周期 & 额外搬运（字节） & 加速比 \\',r'\midrule\endhead']
    tex += [f"{r['case']} & {r['cores']} & {r['makespan']} & {r['added_copy_bytes']} & {r['speedup']:.6f}"+r' \\' for r in rows]
    tex += [r'\bottomrule',r'\end{longtable}']
    (d/'appendix_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc',size=12)
    plt.rcParams.update({'font.size':12,'pdf.fonttype':42,'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(6.0,3.9),layout='constrained')
    for a,label,style,marker,color in [('legacy','原方案','--','s','#666666'),('routed','结构准入方案','-','o','#176b95')]:
        ax.plot(range(1,6),[s['curves'][a][str(k)] for k in range(1,6)],label=label,linestyle=style,marker=marker,color=color,linewidth=1.7,markersize=5)
    ax.set_xticks(range(1,6));ax.set_xlabel('核心数量',fontproperties=font);ax.set_ylabel('平均加速比',fontproperties=font)
    ax.set_ylim(bottom=0.9);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
    ax.legend(prop=font,frameon=False,loc='upper left')
    for ext in ['pdf','png']:fig.savefig(d/f'five_point_curve.{ext}',dpi=300)
    plt.close(fig)
    report=['# 问题二全量审核与结构准入对照 r05','',f"最终全局方案：{arm}；预冻结采用条件：{s['gate']}。全部100图、每图2至5核，两算法均12次机会。未逐例选优。",'',
            '| 核数 | 原方案平均加速比 | 结构准入平均加速比 |','|---|---:|---:|']
    report += [f"| {r['cores']} | {r['legacy']:.6f} | {r['routed']:.6f} |" for r in curves]
    report += ['',f"400个配置胜平负：{s['outcomes']}；逐配置加速比比值的几何平均变化为{(s['geomean_ratio']-1)*100:+.6f}%。该辅助指标不替代题目规定的各核算术平均加速比。",'',
               f"额外搬运与各次搜索墙钟秒数之和：{json.dumps(s['totals'],ensure_ascii=False)}。",'',
               '求解时间只统计B候选搜索；不含Q1迁移种子预生成、固定单核基准和最终独立回放。两方案使用同一批固定种子；该时间不能称完整端到端运行时间。并行工作量之和也不是服务器墙钟时间。','',
               f"预算及一致性核验：{json.dumps({k:v for k,v in s['audit'].items() if k!='invalid_candidates'},ensure_ascii=False)}。未通过候选数：{len(s['audit']['invalid_candidates'])}，详见summary.json。",'',
               '800份方案经官方规则、操作唯一覆盖、Pipe占用、同步时间、搬运恒等式与独立最终回放检查；选定的400份方案额外按真实全局时刻重建物理张量生命周期，全部容量检查通过。100个固定单核分母本轮重新计算，并核对规定基准值。','',
               '原样保留所有退步配置：paired.csv中outcome=loss；selected_500_rows.csv含单核及多核周期、搬运与求解时间；solutions为400份标准命名方案。','',
               '本对照衡量结构准入对完整搜索的影响。两边普通J的生成规则与预算一致，但基础最优解改变时J锚点也会改变，不能将全部收益解释为两个HEFT候选的独立贡献。引导J的固定同基础候选对照已在r03单独报告，本轮未混入该开关。','',
               '100图包含此前开发及确认图，是题目全量基准验证，不是100个全新盲测样本。结构阈值和全量采用条件在本轮评分前冻结；分核配置也不是相互独立的400个数据集。未据此声称统计显著性或对未知模型的泛化保证。','',
               '全量图表和附录数据已具备；正式章节集成、最终排版与人工验收尚未完成，不能据此声明论文全部交付要求已验收。此脚本不更改Q1、不推进工作流门禁、不替换旧q2_submit默认。']
    with (OUT/'all_rows.csv').open(encoding='utf-8-sig') as f:all_rows=list(csv.DictReader(f))
    report += ['','## 耗时与搬运分核统计','', '| 方案 | 核数 | 额外搬运合计/字节 | 搜索中位数/秒 | 搜索最大值/秒 |','|---|---:|---:|---:|---:|']
    for a in ['legacy','routed']:
        for k in range(2,6):
            rr=[r for r in all_rows if r['arm']==a and int(r['cores'])==k]
            seconds=[float(r['solve_seconds']) for r in rr]
            report.append(f"| {a} | {k} | {sum(int(r['bytes']) for r in rr)} | {statistics.median(seconds):.3f} | {max(seconds):.3f} |")
    with (OUT/'paired.csv').open(encoding='utf-8-sig') as f:losses=[r for r in csv.DictReader(f) if r['outcome']=='loss']
    report += ['','## 全部退步配置','', '| 图 | 核数 | 原周期 | 新周期 | 周期增加 |','|---|---:|---:|---:|---:|']
    report += [f"| {r['case']} | {r['cores']} | {r['legacy']} | {r['routed']} | {(int(r['routed'])/int(r['legacy'])-1)*100:.4f}% |" for r in losses]
    if not losses:report.append('无退步配置。')
    (d/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    files=[p for p in d.rglob('*') if p.is_file()]
    write_json(d/'manifest.json',dict(selected_global_algorithm=arm,plans=plans,files={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in files},source_sha256=sha(__import__('pathlib').Path(__file__).read_bytes()),summary_sha256=sha((OUT/'summary.json').read_bytes()),audit_sha256=sha((OUT/'full_audit.json').read_bytes())))
    print(d)


if __name__=='__main__':main()
