"""Report timed software-cache toggle trials and fail closed on expansion."""
import json,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(p):
    c=read(p/'contract.json');files=list((p/'rows').glob('*.json'));rs={f.stem:read(f) for f in files}
    out={'finished':len(rs),'expected':20,'warm_pairs':[],'cold':[],'gate_passed':False,'gate_reasons':[]}
    lines=['# 问题二、三真实搜索的软件准备缓存对照','',
        '只切换软件准备结果缓存，不切换问题三的硬件L2。普通joint候选生成、随机种子、目标函数和96提议上限一致，按已接受方案继续搜索。缓存只改变每次准备耗时及时间预算内可完成的前缀。',
        '小图90秒、大图590秒，均包含最终原版重放与物理内存检查；Q3额外FIFO审计。停止时仅允许返回已经原版验证过的检查点。截止后回退到初解不能伪装成完整完成搜索。','',
        '| 问题/case | 关闭周期 | 开启周期 | 完成评分数 off/on | 总墙钟秒 off/on | 完整结果前缀 |',
        '|---|---:|---:|---:|---:|---|']
    def details(name):
        f=p/'jobs'/name/'details.json'
        if f.exists():return read(f)
        f=p/'jobs'/name/'search.json'
        return read(f) if f.exists() else {'rows':[],'cache_stats':{}}
    for q in [2,3]:
        for i in c['warm_cases'][str(q)]:
            names=[f'q{q}_{i:03}_warm_{m}' for m in ['off','on']]
            if not all(n in rs for n in names):continue
            a,b=[rs[n] for n in names];sa,sb=[r.get('summary',{}) for r in [a,b]];da,db=[details(n) for n in names]
            ta,tb=da['rows'],db['rows'];common=min(len(ta),len(tb));mismatches=[]
            for x,y in zip(ta,tb):
                for field in ['index','incumbent','plan_sha256','status','result_sha256']:
                    if x.get(field)!=y.get(field):mismatches.append(dict(index=x.get('index'),field=field));break
            identities=[read(p/'jobs'/n/'identity.json') for n in names]
            for field in ['input_sha256','seed_sha256','provenance']:
                if identities[0].get(field)!=identities[1].get(field):mismatches.append(dict(field=field))
            final_valid=all(r.get('valid') and r.get('complete') and not r.get('error') for r in [sa,sb])
            v=dict(problem=q,case=i,off=sa.get('makespan'),on=sb.get('makespan'),off_added=sa.get('added'),on_added=sb.get('added'),
                off_seconds=a['external_seconds'],on_seconds=b['external_seconds'],off_scored=sum(x['status']=='ok' for x in ta),on_scored=sum(x['status']=='ok' for x in tb),
                compared_prefix=common,mismatches=mismatches,final_valid=final_valid,off_peak_rss=sa.get('peak_child_rss_bytes'),on_peak_rss=sb.get('peak_child_rss_bytes'),cache_stats=db.get('cache_stats',{}),off_stages=da.get('stages'),on_stages=db.get('stages'))
            if final_valid:v.update(off_speedup=c['fixed_T1'][str(i)]/v['off'],on_speedup=c['fixed_T1'][str(i)]/v['on'])
            matched=[(x,y) for x,y in zip(ta,tb) if x.get('status')==y.get('status')=='ok' and x.get('result_sha256')==y.get('result_sha256') and x.get('plan_sha256')==y.get('plan_sha256')]
            v['matched_score_count']=len(matched)
            v['matched_off_score_seconds']=sum(x['score_seconds'] for x,y in matched)
            v['matched_on_score_seconds']=sum(y['score_seconds'] for x,y in matched)
            stats=v['cache_stats'];v['hit_rate']=stats.get('hits',0)/max(1,stats.get('calls',0))
            out['warm_pairs'].append(v)
            lines.append(f"| Q{q}/{i:03} | {v['off']} | {v['on']} | {v['off_scored']}/{v['on_scored']} | {v['off_seconds']:.2f}/{v['on_seconds']:.2f} | {'一致' if not mismatches else '不一致'}，{common}提议 |")
            if not final_valid:out['gate_reasons'].append(f'Q{q}/{i}: full final verification did not complete')
            if mismatches:out['gate_reasons'].append(f'Q{q}/{i}: candidate/result prefix mismatch')
            if not matched:out['gate_reasons'].append(f'Q{q}/{i}: no shared scored candidate')
            if v['off'] and v['on'] and v['on']>v['off']:out['gate_reasons'].append(f'Q{q}/{i}: makespan regression')
    lines+=['','## 准备缓存与大图压力','',
        '| 问题/case | 命中率 | 淘汰数 | 同候选评分总秒 off/on | 峰值MiB off/on |',
        '|---|---:|---:|---:|---:|']
    for v in out['warm_pairs']:
        lines.append(f"| Q{v['problem']}/{v['case']:03} | {v['hit_rate']:.2%} | {v['cache_stats'].get('evictions',0)} | {v['matched_off_score_seconds']:.2f}/{v['matched_on_score_seconds']:.2f} | {(v['off_peak_rss'] or 0)/1024**2:.1f}/{(v['on_peak_rss'] or 0)/1024**2:.1f} |")
    lines+=['','共享前缀评分总时间只比较相同方案，不包含生成、初解、复核及进程开销；并发共享机器上的单轮计时只能诊断，不能宣称统计显著提速。','', '## 冷启动与时间合规','',
        '冷启动从原图构造Pipe分量装箱初解，生成、搜索及最终验证都计时。这是本轮入口的替代冷初解策略，不是历史Q1→Q2→Q3串联初解生成流程。不得用其耗时证明原串联流程合规，也不得与导入高质量初解的成绩拼接。',
        '固定单核T1仅用于外部统计，不是生成多核方案的必要输入；本轮不计重新计算T1。',
        '| 问题/case | 有效检查点 | 完整结束 | 截止触发 | 总秒数 | 周期 |',
        '|---|---|---|---|---:|---:|']
    for name,r in rs.items():
        s=r.get('summary',{})
        if r['kind']=='cold':
            v=dict(problem=r['problem'],case=r['case'],seconds=r['external_seconds'],valid=s.get('valid'),complete=s.get('complete'),deadline_stop=s.get('deadline_stop'),makespan=s.get('makespan'),peak_rss=s.get('peak_child_rss_bytes'),details=details(name))
            out['cold'].append(v);lines.append(f"| Q{v['problem']}/{v['case']:03} | {v['valid']} | {v['complete']} | {v['deadline_stop']} | {v['seconds']:.2f} | {v['makespan']} |")
            if not v['valid'] or not v['complete']:out['gate_reasons'].append(f"cold Q{v['problem']}/{v['case']}: incomplete")
        if r['external_seconds']>600:out['gate_reasons'].append(name+': >600 seconds')
        if (s.get('peak_child_rss_bytes') or 0)>2*1024**3:out['gate_reasons'].append(name+': >2GiB worker RSS')
    out['problem_metrics']={}
    for q in [2,3]:
        xs=[r for r in out['warm_pairs'] if r['problem']==q and r['final_valid']]
        if len(xs)==len(c['warm_cases'][str(q)]):
            m=dict(off_mean_speedup=sum(r['off_speedup'] for r in xs)/len(xs),on_mean_speedup=sum(r['on_speedup'] for r in xs)/len(xs),off_total_cycles=sum(r['off'] for r in xs),on_total_cycles=sum(r['on'] for r in xs),off_total_added=sum(r['off_added'] for r in xs),on_total_added=sum(r['on_added'] for r in xs))
            out['problem_metrics'][str(q)]=m
            if m['on_mean_speedup']<=m['off_mean_speedup']:out['gate_reasons'].append(f'Q{q}: no strict sample mean speedup improvement')
        else:out['gate_reasons'].append(f'Q{q}: incomplete warm paired sample')
    if len(rs)!=20:out['gate_reasons'].append('20 jobs not finished')
    out['gate_passed']=not out['gate_reasons']
    lines+=['','## 样本成绩（不能代替100图成绩）','',
        '| 问题 | 平均加速比 off/on | 总周期 off/on | 额外搬运字节 off/on |',
        '|---|---:|---:|---:|']
    for q,m in out['problem_metrics'].items():
        lines.append(f"| Q{q} | {m['off_mean_speedup']:.6f}/{m['on_mean_speedup']:.6f} | {m['off_total_cycles']}/{m['on_total_cycles']} | {m['off_total_added']}/{m['on_total_added']} |")
    lines+=['','平均加速比按逐图固定T1/T的算术平均计算；软件准备提速与NPU任务周期下降是两种指标。',
        '预算在创建求解子进程前启动，计入配置/输入读取、初解生成（冷模式）、建模、候选生成、评分、原版全局重放和内存审计；590秒截止后只读取已经验证的检查点。外部墙钟额外覆盖解释器启动和关闭。暖模式读取已有高质量初解，不代表其历史生成时间已计入。',
        '96提议上限是两臂共同安全上限，遇重复不补额外新算子；达到上限后提前返回。未耗满时间时不能把提前返回秒数当作同一完整生产流程的加速。']
    lines+=['','## 决策','',f"扩量门槛：{'通过，仍需冻结全量合同' if out['gate_passed'] else '未通过，不启动100图'}。",'']
    lines+=['- '+r for r in out['gate_reasons']]
    lines+=['','运行在共享服务器，墙钟耗时包含系统负载；小样本单种子结果不等同统计显著性。内存为子进程实测峰值，32MiB只是缓存序列化负载上限，不是进程内存限额。','正式入口、500配置交付和论文未替换，阶段门禁NOT_RUN。']
    lines+=['','## 下一步依据','',
        '本轮Q2/033多评价了7个候选，仅减少16周期、增加6144字节；Q3四组持平。大图072的两问缓存均零命中、各发生204次淘汰，缓存工作集与容量/替换策略不匹配值得优先诊断，尚不能断言单纯扩大容量即可获益。',
        'Q2/072开启臂55提议中40次重复，重复生成约117.45秒；Q3/005开启臂15提议中5次重复，重复生成约39.06秒。应优先复用不变的生成准备，或在昂贵生成前识别等价动作，验证候选顺序和内容不变；不是继续增加关键候选。',
        '当前普通joint追加搜索是控制变量实验，不等于完整组合求解器；96提议上限、保守预留20%复核时间也会限制缓存节省转换为搜索收益。不得据此直接替换正式入口或宣称所有用例10分钟达标。',
        '', '## 复现和验证','',
        '服务器完整启动脚本run_cache_search.py与日志cache_search.log已归档。当前目录须为项目根；求解子进程拒绝复用已有输出目录，但启动脚本会写统计文件。复跑必须在新副本中仅保留合同目录内的contract.json与seeds，避免覆盖本轮证据。服务器使用Python3.12.14和12并发。',
        '`python 程序/q23_cache_search_report.py 图表/runs/20260925-A-q23-cache-search` 重新生成此报告。',
        '`python -m unittest discover -s 程序/tests -p "test_q23_cache*.py" -v` 验证两问缓存前缀一致、无检查点超时失败及有检查点超时保留；后者使用合成故障注入，只验证监督器，不作为官方数值正确性证据。',
        'result_hashes.json核对服务器原始230个产物；server_sources_inputs.json记录287个源码及输入哈希，已与本机一致。派生报告与补充测试在下载后生成，不在原始产物哈希清单中。']
    (p/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(p/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return out

if __name__=='__main__':
    result=report(Path(sys.argv[1]))
    print(json.dumps({k:result[k] for k in ['finished','gate_passed','gate_reasons','problem_metrics']},ensure_ascii=False))
