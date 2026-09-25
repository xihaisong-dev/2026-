"""Audit generation reuse in unchanged, time-adaptive full portfolios."""
import json, sys
from pathlib import Path

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def report(root):
    c=read(root/'contract.json'); errors=[]; jobs=[]; pairs=[]
    for q,cases in c['cases'].items():
        for case in cases:
            arms={}
            for arm in c['arms']:
                name=f'q{q}_{case:03}_{arm}'; p=root/'jobs'/name
                if not (root/'rows'/(name+'.json')).exists():
                    errors.append(name+': missing row'); continue
                r=read(root/'rows'/(name+'.json')); s=r.get('summary',{})
                d=read(p/'details.json') if (p/'details.json').exists() else {}
                search=read(p/'search/search.json') if (p/'search/search.json').exists() else {}
                scores=read(p/'scored.json') if (p/'scored.json').exists() else []
                valid=r['returncode']==0 and s.get('valid') and s.get('complete') and not s.get('error') and s.get('worker_exitcode')==0
                if not valid:errors.append(name+': not completely verified')
                if r['wall']>600:errors.append(name+': wall over 600s')
                a=s.get('arguments',{})
                if any(a.get(k)!=c[k] for k in ['seconds','cores','seed','max_proposals']) or bool(a.get('reuse'))!=(arm=='reuse'):
                    errors.append(name+': arguments mismatch')
                hashes={}
                for x in scores:
                    h=x['plan_sha256']; v=x['result_sha256']
                    if h in hashes and hashes[h]!=v:errors.append(name+': inconsistent repeated official result')
                    hashes[h]=v
                v=dict(problem=int(q),case=case,arm=arm,valid=bool(valid),makespan=s.get('makespan'),added=s.get('added'),seconds=r['wall'],
                    rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2,deadline_stop=s.get('deadline_stop'),scored=len(scores),unique_scored=len(hashes),
                    search_seconds=d.get('search_seconds'),verify_seconds=d.get('final_verify_seconds'),generation_stats=d.get('generation_stats',{}),
                    family_counts=search.get('family_counts',search.get('counts',{})),family_seconds=search.get('family_seconds',search.get('spent',{})))
                jobs.append(v); arms[arm]=(v,hashes,scores,d)
            if len(arms)!=2:continue
            a,ha,sa,da=arms['base']; b,hb,sb,db=arms['reuse']; shared=ha.keys()&hb.keys()
            mismatches=[h for h in shared if ha[h]!=hb[h]]
            if mismatches:errors.append(f'Q{q}/{case}: shared official result mismatch')
            for field in ['input_sha256','provenance']:
                if da.get(field)!=db.get(field):errors.append(f'Q{q}/{case}: {field} mismatch')
            prefix=0
            for x,y in zip(sa,sb):
                if x['plan_sha256']!=y['plan_sha256']:break
                prefix+=1
            pair=dict(problem=int(q),case=case,shared_plans=len(shared),shared_result_mismatches=mismatches,common_scored_prefix=prefix)
            if a['valid'] and b['valid']:
                pair.update(base=a['makespan'],reuse=b['makespan'],cycle_reduction=a['makespan']-b['makespan'],
                    reduction_pct=100*(1-b['makespan']/a['makespan']),added_delta=b['added']-a['added'],
                    base_seconds=a['seconds'],reuse_seconds=b['seconds'],base_scored=a['scored'],reuse_scored=b['scored'])
            pairs.append(pair)
    aggregates={}
    for q in [2,3]:
        aggregates[str(q)]={}
        for arm in c['arms']:
            rows=[x for x in jobs if x['problem']==q and x['arm']==arm and x['valid']]
            if len(rows)==len(c['cases'][str(q)]):
                aggregates[str(q)][arm]=dict(mean_speedup=sum(c['fixed_T1'][str(x['case'])]/x['makespan'] for x in rows)/len(rows),
                    total_cycles=sum(x['makespan'] for x in rows),total_added=sum(x['added'] for x in rows))
    result=dict(errors=errors,jobs=jobs,pairs=pairs,sample_aggregates=aggregates,formal_promoted=False,
        scope='Six selected five-core configurations, one seed, full time-adaptive portfolios. Not 100-case scores or cold end-to-end runtime.')
    (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 完整 protected / combined 生成复用对照','',
        '冻结提交版不变。本轮只切换生成准备复用；软件评价准备缓存关闭，Q3 硬件只读 L2 保持原配置。',
        '每项590秒，搜索截止472秒，剩余时间用于原版完整评价与物理审计；96次提议上限、5核、种子0。导入既有种子的历史生成时间不计入本轮。',
        '原组合按实际耗时自适应选择候选，故加速后搜索序列可以分叉；比较共享方案的完整官方结果哈希，不要求全程候选前缀相同。',
        '',f'检查问题：{len(errors)}；完整通过：{sum(x["valid"] for x in jobs)}/{len(jobs)}；共享方案比较：{sum(x["shared_plans"] for x in pairs)}。','',
        '|问题/case|原组合 cycles|生成复用 cycles|周期下降|额外搬运变化 bytes|官方评分次数 原→复用|总耗时 原→复用 s|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for x in pairs:
        if 'base' not in x:continue
        lines.append(f'|Q{x["problem"]}/{x["case"]:03}|{x["base"]:,}|{x["reuse"]:,}|{x["reduction_pct"]:.4f}%|{x["added_delta"]:+,}|{x["base_scored"]}→{x["reuse_scored"]}|{x["base_seconds"]:.2f}→{x["reuse_seconds"]:.2f}|')
    lines+=['','## 样本汇总（不是全量成绩）','','```json',json.dumps(aggregates,ensure_ascii=False,indent=2),'```','',
        '## 解释限制','',
        '评分更快或评价机会更多不能自动视作周期改善。两臂共用原始候选策略，但实际耗时会改变保护窗口和自适应权重；单种子结果不能隔离调度噪声。',
        '本轮为保留完整组合并包含最终复核的新对照口径，不直接与历史590秒纯搜索成绩作因果比较。没有修改正式入口，没有补齐1～5核全量交付。',
        '复现：按 rows 中 command 在相同依赖环境运行；使用新的输出目录。汇总命令：python 程序/q23_portfolio_reuse_report.py 图表/runs/20260925-A-q23-portfolio-reuse。','']
    if len(pairs)==6 and all(x.get('cycle_reduction')==0 and x.get('added_delta')==0 for x in pairs):
        lines+=['## 本轮决定','',
            '六组周期及搬运量全部持平，不据此替换冻结提交版，也不启动新100图。',
            'Q2/033、067与Q3/005、067均达到96次提议上限，复用没有增加官方评分次数。Q2/072两臂均14次提议、25次评分；Q3/072为35→36次提议、32→33次评分，多一次机会仍未改善。',
            'Q2/072的 order_plan 43次调用全部未命中，累计88.42秒；context 49/55次命中。其瓶颈不是缓存完全失效，而是昂贵排序调用输入不同，整次结果无法复用。后续应先拆分其不变准备与变化部分，单独验证；小图若要利用剩余时间，须另做两臂同时调整提议上限的同预算试验。',
            'Q2/033和067总求解时间分别下降约7.69%与3.46%；Q3/005下降约2.76%，Q3/067反而增加约1.47%。单次共享服务器测量不能宣称稳定提速。',
            '本轮12项完成，最长外部墙钟483.706秒、峰值子进程RSS922.72MiB。导入历史初解，不能据此宣称冷启动十分钟全面达标。','']
    if errors:lines+=['检查问题：',*errors]
    (root/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return result

if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps({k:v for k,v in r.items() if k!='jobs'},ensure_ascii=False,indent=2))
    if r['errors']:raise SystemExit(1)
