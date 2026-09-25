"""Four-arm warm pilot; report failures and unchanged objectives explicitly."""
import json,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def report(p):
    c=read(p/'contract.json');rows=[];comparisons=[];errors=[]
    for q,cases in c['cases'].items():
        for i in cases:
            data={}
            for arm in c['arms']:
                name=f'q{q}_{i:03}_{arm}';f=p/'rows'/(name+'.json')
                if not f.exists():errors.append(name+': missing');continue
                r=read(f);s=r.get('summary',{});d=p/'jobs'/name/'details.json'
                if not (s.get('valid') and s.get('complete') and not s.get('error')):errors.append(name+': incomplete or invalid')
                details=read(d) if d.exists() else {'rows':[]}
                v=dict(problem=int(q),case=i,arm=arm,makespan=s.get('makespan'),added=s.get('added'),seconds=r['seconds'],rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2,
                       proposals=len(details['rows']),scored=sum(x['status']=='ok' for x in details['rows']),generation_seconds=sum(x.get('generation_seconds',0) for x in details['rows']),
                       cache=details.get('cache_stats',{}),generation=details.get('generation_stats',{}))
                rows.append(v);data[arm]=(v,details,read(p/'jobs'/name/'identity.json'))
            if 'base' not in data:continue
            a,da,ia=data['base']
            for arm,(b,db,ib) in data.items():
                if arm=='base':continue
                pairs=list(zip(da['rows'],db['rows']));mismatch=[]
                for x,y in pairs:
                    for k in ['index','incumbent','plan_sha256','status','result_sha256']:
                        if x.get(k)!=y.get(k):mismatch.append(dict(index=x['index'],field=k));break
                for k in ['input_sha256','seed_sha256','provenance']:
                    if ia.get(k)!=ib.get(k):mismatch.append(dict(field=k))
                if mismatch:errors.append(f'{q}/{i}/{arm}: prefix mismatch')
                ga=sum(x.get('generation_seconds',0) for x,y in pairs);gb=sum(y.get('generation_seconds',0) for x,y in pairs)
                score_pairs=[(x,y) for x,y in pairs if x['status']==y['status']=='ok']
                comparisons.append(dict(problem=int(q),case=i,arm=arm,prefix=len(pairs),full_result_pairs=len(score_pairs),mismatch=mismatch,
                    base_generation_seconds=ga,new_generation_seconds=gb,generation_change_pct=100*(gb/ga-1) if ga else None,
                    base_score_seconds=sum(x['score_seconds'] for x,y in score_pairs),new_score_seconds=sum(y['score_seconds'] for x,y in score_pairs),
                    cycle_delta=b['makespan']-a['makespan'] if b['makespan'] and a['makespan'] else None))
    out=dict(rows=rows,comparisons=comparisons,errors=errors,correctness_passed=len(rows)==16 and not errors,formal_promoted=False)
    lines=['# Q2/Q3生成复用与选择性准备缓存四臂试验','',
        '提交候选版本冻结在codex/q23-submit-freeze（ebce54dd）；本实验在独立分支。普通joint候选规则、初解、种子0、最多96提议不变。小图90秒、大图180秒，包含最终原版重放与内存审计；导入历史初解生成时间不计，故仅为暖启动试验。',
        '生成复用只缓存确定性的context、order_plan、proxy，继续消耗原来的随机数序列；同一不可变图上下文内使用，完整参数顺序哈希、隔离副本和32MiB负载上限。准备缓存另设32MiB并按三个阶段分额，第二次访问才准入、过大对象旁路、128次探测零命中后本次关闭该阶段。每个候选的全局DDR/L2模拟仍重算。','',
        '| 问题/图 | 开关 | 周期 | 额外搬运字节 | 评分/提议 | 墙钟秒 | RSS MiB |','|---|---|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| Q{r['problem']}/{r['case']:03} | {r['arm']} | {r['makespan']} | {r['added']} | {r['scored']}/{r['proposals']} | {r['seconds']:.2f} | {r['rss_mib']:.1f} |")
    lines+=['','base=全部关闭，generation=仅生成复用，preparation=仅选择性准备缓存，both=同时开启。','',
        '| 问题/图 | 对照臂 | 共同前缀 | 生成秒 base/new | 评分秒 base/new | 周期差 new-base |','|---|---|---:|---:|---:|---:|']
    for r in comparisons:lines.append(f"| Q{r['problem']}/{r['case']:03} | {r['arm']} | {r['prefix']} | {r['base_generation_seconds']:.2f}/{r['new_generation_seconds']:.2f} | {r['base_score_seconds']:.2f}/{r['new_score_seconds']:.2f} | {r['cycle_delta']} |")
    lines+=['','正确性检查：'+str(out['correctness_passed']),'']+errors
    lines+=['','## 本轮结论','',
        '仅生成复用的四组共同前缀生成耗时下降约36.5%～63.3%，这是候选生成墙钟收益，不是NPU执行周期收益。Q2/033少16周期且多6144字节，其余三组最终周期/搬运持平；同时开启两类缓存也没有额外周期收益。',
        '072的选择性准备缓存仍零命中，本轮没有发生淘汰；绝大多数探测是第一次遇到该完整输入键。旧版零命中不能只归因于容量，本轮未证明扩大缓存可以解决。',
        '保留生成复用作为后续验证重点；选择性准备缓存仅保留实验开关。两者均不写入冻结提交版、不跑新100图。大图180秒短试验只有4～5次完整评分，尚不覆盖长搜索的缓存稳态和收益稳定性。']
    lines+=['','## 边界与后续','',
        '共同前缀逐项比较方案和完整官方结果哈希；单元测试另外检查随机状态和候选序列。并发共享服务器单次墙钟有噪声，本试验不是统计显著性证明，也不是五核100图新成绩。',
        '准备缓存与生成缓存分别限额，两者合用最多64MiB序列化负载，进程RSS另测；缓存开关不是Q3硬件L2开关。',
        '不调整正式入口、既有结果、复核预留或新候选种类。正式门禁NOT_RUN。即使局部耗时下降，也要与最终周期收益分开报告；全量推广仍需独立确认与完整提交覆盖。']
    (p/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (p/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return out
if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps(dict(finished=len(r['rows']),correctness_passed=r['correctness_passed'],errors=r['errors'])))
