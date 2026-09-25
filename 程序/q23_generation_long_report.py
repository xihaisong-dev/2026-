"""Audit long-budget generator reuse without conflating CPU and NPU time."""
import json,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(p):
    c=read(p/'contract.json');pairs=[];errors=[];jobs=[]
    for q,cases in c['cases'].items():
        for case in cases:
            arms={}
            for arm in c['arms']:
                name=f'q{q}_{case:03}_{arm}';f=p/'rows'/(name+'.json');job=p/'jobs'/name
                if not f.exists():errors.append(name+': missing');continue
                r=read(f);s=r.get('summary',{});d=read(job/'details.json') if (job/'details.json').exists() else {'rows':[]}
                valid=r.get('exitcode')==0 and s.get('valid') and s.get('complete') and not s.get('error') and s.get('worker_exitcode')==0
                if not valid:errors.append(name+': not completely verified')
                if r['seconds']>600:errors.append(name+': over 600s')
                a=s.get('arguments',{})
                if a.get('seconds')!=590 or a.get('max_proposals')!=384 or a.get('seed')!=0 or a.get('mode')!='off' or bool(a.get('generation_reuse'))!=(arm=='generation'):
                    errors.append(name+': argument mismatch')
                v=dict(problem=int(q),case=case,arm=arm,valid=bool(valid),makespan=s.get('makespan'),added=s.get('added'),seconds=r['seconds'],
                       rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2,deadline_stop=s.get('deadline_stop'),proposals=len(d['rows']),
                       scored=sum(x['status']=='ok' for x in d['rows']),duplicates=sum(x['status']=='duplicate' for x in d['rows']),
                       generation_seconds=sum(x.get('generation_seconds',0) for x in d['rows']),generation_stats=d.get('generation_stats',{}),stages=d.get('stages',{}),
                       last_accepted_index=max((x['index'] for x in d['rows'] if x.get('accepted')),default=None))
                jobs.append(v);arms[arm]=(v,d,read(job/'identity.json') if (job/'identity.json').exists() else {})
            if len(arms)!=2:continue
            a,da,ia=arms['base'];b,db,ib=arms['generation'];common=list(zip(da['rows'],db['rows']));mismatch=[]
            for x,y in common:
                for field in ['index','incumbent','plan_sha256','status','result_sha256','accepted']:
                    if x.get(field)!=y.get(field):mismatch.append(dict(index=x.get('index'),field=field));break
            for field in ['input_sha256','seed_sha256','provenance']:
                if ia.get(field)!=ib.get(field):mismatch.append(dict(field=field))
            if mismatch:errors.append(f'Q{q}/{case}: prefix mismatch')
            scores=[(x,y) for x,y in common if x.get('status')==y.get('status')=='ok']
            ga=sum(x.get('generation_seconds',0) for x,y in common);gb=sum(y.get('generation_seconds',0) for x,y in common)
            item=dict(problem=int(q),case=case,base=a,generation=b,prefix=len(common),full_result_comparisons=len(scores),mismatches=mismatch,
                      common_base_generation_seconds=ga,common_new_generation_seconds=gb,generation_change_pct=100*(gb/ga-1) if ga else None,
                      common_base_score_seconds=sum(x['score_seconds'] for x,y in scores),common_new_score_seconds=sum(y['score_seconds'] for x,y in scores),
                      extra_accepted=[x['index'] for x in db['rows'][len(da['rows']):] if x.get('accepted')])
            if a['valid'] and b['valid']:
                item.update(cycle_delta=b['makespan']-a['makespan'],added_delta=b['added']-a['added'],base_speedup=c['fixed_T1'][str(case)]/a['makespan'],new_speedup=c['fixed_T1'][str(case)]/b['makespan'])
            pairs.append(item)
    metrics={}
    for q,cases in c['cases'].items():
        xs=[x for x in pairs if x['problem']==int(q) and 'cycle_delta' in x]
        if len(xs)!=len(cases):continue
        metrics[q]=dict(count=len(xs),base_mean_speedup=sum(x['base_speedup'] for x in xs)/len(xs),new_mean_speedup=sum(x['new_speedup'] for x in xs)/len(xs),
            base_cycles=sum(x['base']['makespan'] for x in xs),new_cycles=sum(x['generation']['makespan'] for x in xs),base_added=sum(x['base']['added'] for x in xs),new_added=sum(x['generation']['added'] for x in xs),
            wins=sum(x['cycle_delta']<0 for x in xs),ties=sum(x['cycle_delta']==0 for x in xs),losses=sum(x['cycle_delta']>0 for x in xs))
    result=dict(jobs=len(jobs),expected=12,correctness_passed=len(jobs)==12 and not errors,errors=errors,pairs=pairs,metrics=metrics,formal_promoted=False)
    if not result['correctness_passed']:decision='正确性或完整性未通过，停止推广。'
    elif any(x.get('cycle_delta',0)>0 for x in pairs):decision='存在周期退步，需要定位预算与截止差异；不推广。'
    elif any(x.get('cycle_delta',0)<0 for x in pairs):decision='长预算样本出现周期收益，可进一步做完整组合对照；尚不自动推广到提交版。'
    elif any(x.get('added_delta',0)<0 for x in pairs):decision='周期持平，存在等周期少搬运收益；不宣称周期加速。'
    else:decision='长预算最终周期没有改善；生成省时和额外搜索机会尚未转化为更优方案。'
    result['decision']=decision
    lines=['# 生成复用590秒长预算配对验证','',
        '普通joint候选规则、初解与种子0固定，只切换生成复用；准备缓存关闭。两臂均590秒含最终原版重放及物理内存审计；两臂提议上限同时提高到384，避免96上限提前截断长预算。不把本轮与旧96上限试验作同预算收益比较。',
        '固定20%及实测原版复核成本预留不变；所有输入均为导入历史高质量初解，初解历史生成不计，因此是暖启动实验。不是最新protected/combined完整组合的验证，不覆盖全部100图。','',
        '| 问题/图 | 周期 off/on | 评分数 off/on | 提议数 off/on | 总秒数 off/on |',
        '|---|---:|---:|---:|---:|']
    for x in pairs:
        a,b=x['base'],x['generation'];lines.append(f"| Q{x['problem']}/{x['case']:03} | {a['makespan']}/{b['makespan']} | {a['scored']}/{b['scored']} | {a['proposals']}/{b['proposals']} | {a['seconds']:.2f}/{b['seconds']:.2f} |")
    lines+=['','## 共同前缀与归因','',
        '| 问题/图 | 前缀/完整评分对照数 | 生成秒 off/on | 评分秒 off/on | 额外前缀中的接受索引 |',
        '|---|---:|---:|---:|---|']
    for x in pairs:lines.append(f"| Q{x['problem']}/{x['case']:03} | {x['prefix']}/{x['full_result_comparisons']} | {x['common_base_generation_seconds']:.2f}/{x['common_new_generation_seconds']:.2f} | {x['common_base_score_seconds']:.2f}/{x['common_new_score_seconds']:.2f} | {x['extra_accepted']} |")
    lines+=['','候选计划、接受决定、当前最优计划与完整官方结果逐前缀核对；生成与评分耗时分别报告。并发同服务器仍存在系统负载噪声，单种子结果不能宣称统计显著性。','',
        '## 小样本汇总（非100图新成绩）','',
        '| 问题 | 平均加速比 off/on | 周期合计 off/on | 额外搬运 off/on | 周期胜/平/负 |','|---|---:|---:|---:|---:|']
    for q,m in metrics.items():lines.append(f"| Q{q} | {m['base_mean_speedup']:.6f}/{m['new_mean_speedup']:.6f} | {m['base_cycles']}/{m['new_cycles']} | {m['base_added']}/{m['new_added']} | {m['wins']}/{m['ties']}/{m['losses']} |")
    lines+=['','完整性与正确性：'+str(result['correctness_passed'])]+['- '+e for e in errors]
    lines+=['','## 决策','',decision]
    lines+=['','最大外部墙钟秒：'+str(max((x['seconds'] for x in jobs),default=None)), '最大RSS MiB：'+str(max((x['rss_mib'] for x in jobs),default=None)),
        '冻结提交分支codex/q23-submit-freeze（ebce54dd）保持不变，正式门禁NOT_RUN。未执行新100图和完整组合推广。',
        '', '复算：`python 程序/q23_generation_long_report.py 图表/runs/20260925-A-q23-generation-long`。实际运行脚本及日志随证据目录归档；复跑必须使用新目录，不能覆盖当前结果。']
    (p/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (p/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return result

if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps({k:r[k] for k in ['jobs','correctness_passed','errors','metrics']},ensure_ascii=False))
