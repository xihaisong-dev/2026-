"""Audit observed rewards, deterministic choices and independent official output."""
import json,random,sys
from collections import Counter
from pathlib import Path
from q23_reward_prefix import choose,reward

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(root):
    c=read(root/'contract.json');errors=[];jobs=[];pairs=[]
    for n in c['cases']['3']:
        arms={}
        for arm in c['arms']:
            name=f'q3_{n:03}_{arm}';p=root/'jobs'/name;r=read(root/'rows'/(name+'.json'));s=r['summary'];a=s['arguments']
            d=read(p/'details.json') if (p/'details.json').exists() else {}
            t=read(p/'search/search.json') if (p/'search/search.json').exists() else {}
            identity=read(p/'search/identity.json');scores=read(p/'scored.json') if (p/'scored.json').exists() else []
            valid=s.get('valid') and s.get('complete') and not s.get('error') and not s.get('deadline_stop') and s.get('worker_exitcode')==0 and r['returncode']==0
            if not valid or r['wall']>600:errors.append(name+': verification or deadline')
            if any(a[k]!=c[k] for k in ['seconds','cores','seed','max_proposals']) or not a['reuse'] or bool(a['ordering_prepare'])!=(arm=='prepared') or a['policy']!=('reward' if arm in ['reward','prepared'] else arm):errors.append(name+': arguments')
            byhash={x['plan_sha256']:x for x in scores}
            if arm in ['reward','prepared']:
                counts=Counter();gains=Counter();rng=random.Random(a['seed']+0x51EC70)
                for x in t.get('proposals',[]):
                    f,w=choose(x['index'],identity['prefix'],identity['extension_cycle'],counts,gains,rng)
                    if f!=x['family'] or w!=x.get('selection_weights'):errors.append(name+': weights/choice replay')
                    counts[f]+=1
                    value=0.
                    if x.get('accepted'):
                        before=byhash[x['incumbent']];after=byhash[x['plan_sha256']]
                        value=reward((before['makespan'],before['added']),(after['makespan'],after['added']))
                    if value!=x.get('reward',0.):errors.append(name+': reward replay')
                    gains[f]+=value
            row=dict(case=n,arm=arm,valid=bool(valid),makespan=s.get('makespan'),added=s.get('added'),seconds=r['wall'],scored=len(scores),proposals=len(t['proposals']) if 'proposals' in t else sum(t.get('family_counts',t.get('counts',{})).values()),rss_mib=(s.get('peak_child_rss_bytes') or 0)/1024**2,counts=t.get('family_counts',t.get('counts',{})),gains=t.get('gains',{}))
            jobs.append(row);arms[arm]=(row,t,byhash,d,identity)
        a,ta,ha,da,ia=arms['reward'];b,tb,hb,db,ib=arms['prepared']
        fields=['index','family','step','phase','incumbent','plan_sha256','status','accepted','reward','selection_weights','error']
        common=list(zip(ta.get('proposals',[]),tb.get('proposals',[])))
        mismatches=[x['index'] for x,y in common if any(x.get(k)!=y.get(k) for k in fields)]
        if mismatches:errors.append(f'{n}: reward/prepared prefix')
        ea,eb=ta.get('evaluations',[]),tb.get('evaluations',[])
        for x,y in zip(ea,eb):
            if any(x.get(k)!=y.get(k) for k in ['name','status','plan_sha256','accepted','makespan','added_copy_bytes','error']):errors.append(f'{n}: evaluation prefix')
        for k in ['input_sha256','provenance']:
            if da.get(k)!=db.get(k):errors.append(f'{n}: input difference')
        shared=ha.keys()&hb.keys()
        if any(ha[h]['result_sha256']!=hb[h]['result_sha256'] for h in shared):errors.append(f'{n}: full result difference')
        foundation=list(zip(arms['stable'][1].get('proposals',[]),ta.get('proposals',[])))[:len(ia['prefix'])]
        if any(any(x.get(k)!=y.get(k) for k in ['index','family','step','incumbent','plan_sha256','status','accepted']) for x,y in foundation):errors.append(f'{n}: foundation changed')
        legacy=arms['legacy'][0];fixed=arms['stable'][0]
        p=dict(case=n,legacy=legacy['makespan'],stable=fixed['makespan'],reward=a['makespan'],prepared=b['makespan'],common_proposals=len(common),shared_results=len(shared),foundation_checked=len(foundation),
            reward_scored=a['scored'],prepared_scored=b['scored'],covers=a['proposals']<=b['proposals'] and len(ea)<=len(eb) and len(ha)<=len(hb),
            reward_added=a['added'],prepared_added=b['added'])
        if p['covers'] and a['valid'] and b['valid'] and (b['makespan'],b['added'])>(a['makespan'],a['added']):errors.append(f'{n}: covered prefix regressed')
        pairs.append(p)
    null=root/'ablation_null';ns=read(null/'summary.json');nt=read(null/'search/search.json');ni=read(null/'search/identity.json')
    if not ns.get('valid') or not ns.get('complete') or ns.get('error') or ns.get('deadline_stop') or ns.get('worker_exitcode')!=0:errors.append('prior-only control: invalid')
    if any(ns['arguments'][k]!=c[k] for k in ['seconds','cores','seed','max_proposals']) or ns['arguments'].get('ordering_prepare') or ns['arguments'].get('ablation')!='prior_only_selection':errors.append('prior-only control: arguments')
    rng=random.Random(ns['arguments']['seed']+0x51EC70);counts=Counter()
    for x in nt.get('proposals',[]):
        f,w=choose(x['index'],ni['prefix'],ni['extension_cycle'],counts,Counter(),rng)
        if f!=x['family'] or w!=x.get('selection_weights'):errors.append('prior-only control: selection replay')
        counts[f]+=1
    null_result=dict(case=5,makespan=ns.get('makespan'),added=ns.get('added'),seconds=ns['total_seconds'],proposals=len(nt.get('proposals',[])),valid=ns.get('valid') and ns.get('complete'))
    result=dict(errors=errors,jobs=jobs,pairs=pairs,prior_only_control=null_result,formal_promoted=False)
    (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Q3 不依赖墙钟的候选权重验证','',
        '保持原基础前缀与候选实现，只替换追加阶段的选择。对类别f，权重为 prior(f) × [1 + min(8, 100 × 累计奖励(f) / max(1,尝试次数(f)))]。',
        '奖励优先取实际官方周期相对下降；周期相等且额外搬运下降时，取搬运下降比例×0.001。拒绝、重复、无效及耗尽候选奖励0，仍计入尝试次数。正式接受始终按(Makespan,额外搬运)字典序，不修改物理目标。',
        '追加阶段偶数位继续固定结构轮转，奇数位按上述权重抽样；选择器使用与候选生成独立的固定种子。权重只读取已验证改善和次数，不读取实际耗时。墙钟只用于停止与最终复核预留。',
        '四臂：旧组合、固定轮转、收益权重、收益权重＋准备复用；均启用原生成复用，590秒、5核、种子0、384提议上限，20%预算留最终原版复核。005为上一轮退步图，044为额外验证图，072为大图。没有按case编号选择算子。',
        '', '|case|旧组合|固定轮转|收益权重|收益权重＋复用|评分 权重→复用|','|---|---:|---:|---:|---:|---:|']
    for p in pairs:lines.append(f'|{p["case"]:03}|{p["legacy"]}|{p["stable"]}|{p["reward"]}|{p["prepared"]}|{p["reward_scored"]}→{p["prepared_scored"]}|')
    lines+=['',f'完整复核{sum(x["valid"] for x in jobs)}/{len(jobs)}；共同提议{sum(x["common_proposals"] for x in pairs)}；完整结果哈希{sum(x["shared_results"] for x in pairs)}；检查问题{len(errors)}。',
        f'最长墙钟{max(x["seconds"] for x in jobs):.3f}秒，峰值子进程RSS{max(x["rss_mib"] for x in jobs):.2f}MiB。',
        '报告逐步重算了每次奖励、权重和抽样类别，并核对固定轮转与收益策略共同的基础前缀；完整官方评价仍重新计算全局依赖和DDR竞争。',
        '', '## 限制与复现','',
        '单种子三图不能替代100图成绩，也不能保证找回旧随机路径的某个特定方案。暖初解历史生成不计，不宣称冷启动十分钟全面满足。冻结提交版未替换；正式门禁NOT_RUN。',
        '逐项运行命令见rows/*.json.command；换新输出目录复跑。汇总：python 程序/q3_reward_prefix_report.py 图表/runs/20260925-A-q3-reward-prefix。','']
    lines+=['## 005奖励项消融','',
        f'额外控制仅在选择时将gains置零，保留相同先验、固定探索、独立随机种子及全部正式评价。得到{null_result["makespan"]}周期，{null_result["proposals"]}次提议，用时{null_result["seconds"]:.3f}秒。',
        '该控制的summary.arguments.ablation与ablation_contract.json说明实际策略；共享包装器details.policy为继承标签，以重放后的实际selection_weights为准。',
        '对照是补充的单图单种子消融，运行负载不完全相同；若两臂都达到384次提议上限，可以比较同提议上限下的方案质量，但不宣称统计显著性。','']
    lines+=['## 本轮结论','',
        '三图相对旧组合一胜两平。005从42856降到42541周期（下降0.7350%），额外搬运减少4736字节；相对固定轮转43163周期下降1.4410%。044与072持平。',
        '005奖励关闭为42721周期；开启奖励再减少180周期（0.4213%）与1920字节。两臂均完成384次提议，支持奖励项在这张图上有效，但不是全量泛化证明。',
        '准备复用保持803次共同提议和481份完整评价结果一致，评分总数481→482；本轮未带来额外最终周期收益。有效改善来自候选选择规则。',
        '决策：保留实验分支，下一步在未参与规则选择的图和多种子上做同预算验证，再决定是否替换冻结组合；不更新正式全量成绩。','']
    (root/'README.md').write_text('\n'.join(lines),encoding='utf-8');return result

if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps(r['pairs'],indent=2));print(r['errors'])
    if r['errors']:raise SystemExit(1)
