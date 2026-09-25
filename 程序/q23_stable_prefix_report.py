"""Audit common-prefix preservation separately from legacy quality comparison."""
import json,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(root):
    c=read(root/'contract.json');errors=[];jobs=[];pairs=[]
    for q,cases in c['cases'].items():
        for case in cases:
            arms={}
            for arm in c['arms']:
                name=f'q{q}_{case:03}_{arm}';p=root/'jobs'/name
                r=read(root/'rows'/(name+'.json'));s=r['summary'];a=s['arguments']
                d=read(p/'details.json') if (p/'details.json').exists() else {}
                trace=read(p/'search/search.json') if (p/'search/search.json').exists() else {}
                scores=read(p/'scored.json') if (p/'scored.json').exists() else []
                valid=all([s.get('valid'),s.get('complete'),not s.get('error'),not s.get('deadline_stop'),s.get('worker_exitcode')==0,r['returncode']==0])
                if not valid or r['wall']>600:errors.append(name+': invalid/over deadline')
                if any(a[k]!=c[k] for k in ['seconds','cores','seed','max_proposals']) or not a['reuse'] or bool(a['ordering_prepare'])!=(arm=='prepared') or a['policy']!=('legacy' if arm=='legacy' else 'stable'):
                    errors.append(name+': argument mismatch')
                row=dict(problem=int(q),case=case,arm=arm,valid=valid,makespan=s.get('makespan'),added=s.get('added'),seconds=r['wall'],scored=len(scores),rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2,
                    counts=trace.get('family_counts',trace.get('counts',{})),proposals=len(trace.get('proposals',[])),stats=d.get('generation_stats',{}))
                jobs.append(row);arms[arm]=(row,trace,scores,d)
            a,ta,sa,da=arms['stable'];b,tb,sb,db=arms['prepared'];legacy=arms['legacy'][0]
            differences=[]
            fields=['index','family','step','phase','incumbent','plan_sha256','status','accepted','error']
            common=list(zip(ta.get('proposals',[]),tb.get('proposals',[])))
            for x,y in common:
                if any(x.get(k)!=y.get(k) for k in fields):differences.append(x['index'])
            ea,eb=ta.get('evaluations',[]),tb.get('evaluations',[])
            for i,(x,y) in enumerate(zip(ea,eb)):
                if any(x.get(k)!=y.get(k) for k in ['name','status','plan_sha256','accepted','makespan','added_copy_bytes','error']):differences.append('eval_'+str(i))
            ha={x['plan_sha256']:x['result_sha256'] for x in sa};hb={x['plan_sha256']:x['result_sha256'] for x in sb};shared=ha.keys()&hb.keys()
            if differences:errors.append(f'Q{q}/{case}: prefix mismatch')
            if any(ha[h]!=hb[h] for h in shared):errors.append(f'Q{q}/{case}: complete official result mismatch')
            if any(da.get(k)!=db.get(k) for k in ['input_sha256','provenance']):errors.append(f'Q{q}/{case}: inputs mismatch')
            pair=dict(problem=int(q),case=case,common_proposals=len(common),prefix_mismatches=differences,shared_full_results=len(shared),
                stable=a['makespan'],prepared=b['makespan'],legacy=legacy['makespan'],
                prepared_minus_stable=b['makespan']-a['makespan'] if a['valid'] and b['valid'] else None,
                prepared_minus_legacy=b['makespan']-legacy['makespan'] if b['valid'] and legacy['valid'] else None,
                added_delta=b['added']-a['added'] if a['valid'] and b['valid'] else None,
                prepared_covers_stable=not differences and a['valid'] and b['valid'] and a['proposals']<=b['proposals'] and len(ea)<=len(eb) and len(sa)<=len(sb),stable_proposals=a['proposals'],prepared_proposals=b['proposals'],stable_scored=a['scored'],prepared_scored=b['scored'])
            pairs.append(pair)
            if pair['prepared_covers_stable'] and (b['makespan'],b['added'])>(a['makespan'],a['added']):
                errors.append(f'Q{q}/{case}: covered prefix but final objective regressed')
    r=dict(errors=errors,jobs=jobs,pairs=pairs,formal_promoted=False)
    (root/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 固定基础序列与追加搜索验证','',
        '本轮不读取历史候选台账或按case编号选算法。Q2保留迁移、整图、原初解菜单和4个ordinary_J机会；Q3保留最新Q2初解与原Q3锚点。',
        '新序列：Q2先4次joint，Q3先4对cache/joint；随后按结构先验权重轮转order、remap、insert、granularity、frontier、packing、joint、cache（只含适用者）。基础首轮后继续相同周期。实际耗时只决定停止，不决定类别、权重或随机种子。',
        '该序列是新规则，不声称重现旧耗时自适应序列。三臂是旧组合、新序列、新序列加排序准备复用；全部开启上一轮生成复用，590秒含最终原版重放及物理审计，种子0、5核、384次提议上限。旧组合也采用384上限，不能与此前96上限直接归因比较。',
        '', '|问题/case|旧组合周期|固定序列周期|固定序列＋复用周期|复用对固定序列变化|提议 固定→复用|评分 固定→复用|','|---|---:|---:|---:|---:|---:|---:|']
    for x in pairs:lines.append(f'|Q{x["problem"]}/{x["case"]:03}|{x["legacy"]}|{x["stable"]}|{x["prepared"]}|{x["prepared_minus_stable"]}|{x["stable_proposals"]}→{x["prepared_proposals"]}|{x["stable_scored"]}→{x["prepared_scored"]}|')
    lines+=['',f'完整复核{sum(x["valid"] for x in jobs)}/{len(jobs)}；共同提议{sum(x["common_proposals"] for x in pairs)}；共同方案完整结果核对{sum(x["shared_full_results"] for x in pairs)}；检查问题{len(errors)}。',
        f'最长外部墙钟{max(x["seconds"] for x in jobs):.3f}秒，峰值子进程RSS{max(x["rss_mib"] for x in jobs):.2f}MiB。',
        '', '## 解释与限制','',
        '复用臂覆盖固定序列基线的全部候选时，在评价确定且择优接受的条件下才能保证本轮不退步。更快并不自动保证覆盖，必须检查实测前缀长度；也不保证新固定序列优于旧组合。',
        '追加搜索由剩余墙钟时间驱动，没有凭空授予复用臂额外时间。固定序列两臂的共同提议、接受决策、初始评价序列和完整官方结果均核对。',
        '单种子四组是诊断，不能更新全100图成绩。导入初解历史生成不计，不宣称冷启动十分钟全面达标。冻结提交版、原完整求解器与正式入口不变；正式门禁NOT_RUN。',
        '逐项真实命令见rows；复跑必须换输出目录。汇总命令：python 程序/q23_stable_prefix_report.py 图表/runs/20260925-A-q23-stable-prefix。','']
    lines+=['## 本轮决定','',
        '四组复用臂均覆盖固定序列基线，808共同提议完全一致、426共同方案完整官方结果一致；评分426→428，但周期与搬运四组均持平。Q2/072及Q3/072各多一次提议/评分，没有改善最终方案。',
        '相对本轮384提议上限的旧组合：Q2/033下降2137周期（0.602%），Q2/072下降21452周期（0.446%），Q3/005增加307周期（0.716%），Q3/072持平。这不是相对冻结100图结果的新成绩。',
        'Q3/005的旧组合经cache/joint多次改善，最后由insert达到42856；新序列得到43163，旧组合最终方案未进入新序列候选池。确定性修复了耗时扰动，但当前固定轮转仍可能损失有效探索。',
        '因此不替换冻结提交版。后续可单独比较按改善量/尝试次数调整的确定性权重，保留基础序列及探索下限，避免回到依赖瞬时耗时的选择；此方向本轮未实现或验证。','']
    (root/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return r

if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps(r['pairs'],indent=2));print(r['errors'])
    if r['errors']:raise SystemExit(1)
