"""Summarize negative as well as positive results without replacing official runs."""
import json,sys
from pathlib import Path
from collections import defaultdict,Counter

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(p):
    contract=read(p/'trial_contract.json');diagnosis=read(p/'diagnosis.json');summary={'problems':{},'reuse':{},'promote_full100':False}
    q3stats=defaultdict(Counter)
    for f in (p/'logs/q3/jobs').glob('*_combined/search.json'):
        search=read(f);best=None
        for name,n in search.get('family_counts',{}).items():q3stats[name]['proposals']+=n
        for r in search['evaluations']:
            a=q3stats[r['name']];a[r['status']]+=1;a['recorded_seconds']+=r.get('seconds',0)
            if r.get('accepted'):a['accepted']+=1
            if r['status']=='ok':
                obj=(r['makespan'],r['added_copy_bytes'])
                if best:
                    a['accepted_cycle_gain']+=max(0,best[0]-obj[0])
                    if obj[0]==best[0] and obj[1]<best[1]:a['same_cycle_byte_gain']+=best[1]-obj[1]
                best=min(best,obj) if best else obj
    for a in q3stats.values():
        if 'proposals' in a:a['unscored_proposals']=a['proposals']-a['ok']-a['invalid']-a['generation_invalid']
    summary['q3_historical_family_stats']={k:dict(v) for k,v in q3stats.items()}
    lines=['# 问题二、三预算诊断及小范围验证','',
        '结论：本轮两个引导候选方案均未通过事前扩量条件；准备结果复用正确但冷缓存成本上升，不接入默认算法，不新跑100图，不更新正式成绩。','',
        '## 现有日志诊断','',
        '问题二保护组合相对延长普通搜索退步的16图：'+ '、'.join(f'{i:03}' for i in diagnosis['loss_cases'])+'。',
        '这些图合计多16427周期。基础joint有效评分851→379，所占已记录评价时间71.22%→29.50%；新增类别813次提议、235次重复，共耗已记录813.40秒，直接接受的周期收益仅679。',
        '这是机会成本和路径分叉的证据，不是反事实因果证明；两条路径从同一前缀分叉后，后续候选也会变化。重复提议的0秒记录不包括完整生成、哈希成本，不可当作真实零开销。','',
        '| case | 普通搜索周期 | 保护组合周期 | 多用周期 | joint有效评分（普通/组合） |',
        '|---|---:|---:|---:|---:|']
    for r in sorted(diagnosis['cases'],key=lambda r:-r['regression_cycles']):
        lines.append(f"| {r['case']:03} | {r['ordinary']} | {r['protected']} | {r['regression_cycles']} | {r['ordinary_joint_scored']}/{r['protected_joint_scored']} |")
    lines+=['','问题二逐类别改善、重复率、时间份额及全部100图统计见 diagnosis.json；问题三逐类别统计见 trial_summary.json 的 q3_historical_family_stats。Q3未评分提议含重复与邻域耗尽，旧日志无法将两者分开，不能作为精确重复率。候选收益按实际接受路径累计，不叠加重叠的关键路径或DDR等待。','',
        '## 小试验合同与结果','',
        '统一五核、90秒暖启动总预算（含初始评价、诊断、候选生成和最终原版重放/物理内存审计），最多16个去重候选，种子0。实际候选不足则如实停止，不补成穷举。',
        '问题二使用最新protected方案作起点，对照16个普通局部候选；引导组保留前8个基础候选，再加入至多8个关键等待迁移/边界与映射联合候选。',
        '问题三使用最新combined方案作起点，严格固定节点划分及核心归属，对比普通同核顺序候选与关键重复未命中/淘汰关系引导顺序候选。',
        '这些是历史图上的开发验证，不是未见图泛化证据。源文件版本与种子哈希见 trial_contract.json；原版源码快照在本地部署ZIP中保留。','',
        '| 问题/case | 对照周期 | 引导周期 | 对照/引导评分数 | 引导总秒数（含复核） |',
        '|---|---:|---:|---:|---:|']
    all_summaries=[]
    for q in [2,3]:
        pairs=[];logcontract=read(p/f'logs/q{q}/contract.json')
        for i in contract[f'q{q}_cases']:
            out={a:read(p/f'trials/q{q}_{i:03}_{a}/summary.json') for a in contract['arms']}
            details={a:read(p/f'trials/q{q}_{i:03}_{a}/details.json') for a in contract['arms']}
            all_summaries+=list(out.values());single=logcontract['baseline'][str(i)]['single'] if q==2 else logcontract['seeds'][f'case_{i:03}_multicore_res.json']['single']
            a,b=out['control'],out['guided'];pairs.append(dict(case=i,control=a['makespan'],guided=b['makespan'],control_bytes=a['added'],guided_bytes=b['added'],single=single))
            lines.append(f"| Q{q}/{i:03} | {a['makespan']} | {b['makespan']} | {len(details['control']['evaluations'])}/{len(details['guided']['evaluations'])} | {b['total_seconds']:.3f} |")
        stats=dict(pairs=pairs,wins=sum(r['guided']<r['control'] for r in pairs),ties=sum(r['guided']==r['control'] for r in pairs),losses=sum(r['guided']>r['control'] for r in pairs),
            mean_control_speedup=sum(r['single']/r['control'] for r in pairs)/len(pairs),mean_guided_speedup=sum(r['single']/r['guided'] for r in pairs)/len(pairs),
            control_cycles=sum(r['control'] for r in pairs),guided_cycles=sum(r['guided'] for r in pairs))
        summary['problems'][str(q)]=stats
    lines+=['','问题二5平1负，问题三1胜1平2负。问题二033仍被挤掉有效基础候选；问题三044/046引导组均只有1个候选，说明只看一条关键链上的重复未命中会使邻域过窄。',
        '不采用逐图挑选对照/引导较好者充当新算法。若继续修订，应先保持完整基础候选序列，对引导池去重后的空缺回填基础候选，并记录耗时，而不是继续新增搜索类别。','',
        '## 等价准备复用','',
        '只缓存Step1核内顺序、Step2换入换出及Step3执行准备。键包含完整有序输入和硬件参数；进程内限定缓存，按序列化体积32MiB淘汰（不是实际进程内存上限）。深复制隔离官方模拟的可变状态。每个候选均重新运行全局依赖、DDR及L2竞争，不缓存全局时长。',
        '本机与服务器各2项单测通过：顺序、带宽、Cache配置改变后完整结果一致；异常退出恢复原函数。实际候选池对照顺序为原版→复用，每图两次独立冷缓存重复，每次另跑同池暖缓存；是微基准，未随机化执行顺序，不能作为稳健生产加速承诺。','',
        '| 问题/case | 完整字段一致次数 | 冷缓存耗时变化 | 重复池暖缓存耗时变化 |',
        '|---|---:|---:|---:|']
    for f in sorted((p/'trials').glob('*/reuse_benchmark.json')):
        rs=read(f)['rows'];v={'equal_count':len(rs),'all_equal':all(r['equal'] for r in rs)}
        for phase in ['cold','warm']:
            xs=[r for r in rs if r['phase']==phase];a=sum(r['original_seconds'] for r in xs);b=sum(r['reuse_seconds'] for r in xs)
            v[phase]=dict(original_seconds=a,reuse_seconds=b,change_percent=(b/a-1)*100)
        summary['reuse'][f.parent.name]=v
        lines.append(f"| {f.parent.name} | {len(rs)} | {v['cold']['change_percent']:+.3f}% | {v['warm']['change_percent']:+.3f}% |")
    summary['verified_trials']=sum(r['valid'] and r['complete'] and not r['error'] for r in all_summaries)
    summary['max_including_audit_seconds']=max(r['total_seconds'] for r in all_summaries)
    summary['same_cycle_byte_improvements']=sum(r.get('same_cycle_less_bytes',False) for f in (p/'trials').glob('*/details.json') for r in read(f)['evaluations'])
    lines+=['','冷批次全部变慢，新增哈希、序列化和复制成本超过当批复用收益；暖池仅约3%～13%节省，不代表正常搜索命中率。当前去重搜索通常不会重评同一完整方案，所以默认不启用。后续先减少快照开销，并用不重复的真实候选流重新验证。','',
        '## 次目标与时间边界','',
        '原日志已包含等周期减少搬运：普通joint累计540388字节、protected joint累计512360字节；是不同路径中的累计次目标改善，不是最终两方案字节差。当前20项试验未发现新的等周期减搬运接受动作（0次），没有凭空宣称收益。',
        f"20项全部原版重放及实际物理内存核验通过，最长含必要复核耗时{summary['max_including_audit_seconds']:.3f}秒；Q3另核验FIFO。暖启动种子生成及固定T1仍不在本轮90秒中。小中图通过不代表100图冷启动10分钟合规。",'','正式阶段门禁 NOT_RUN。旧500组、正式入口和论文成绩保持不变。']
    (p/'trial_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (p/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary

if __name__=='__main__':print(json.dumps(report(Path(sys.argv[1])),ensure_ascii=False))
