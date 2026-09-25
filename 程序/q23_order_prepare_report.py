"""Separate fixed-work costs, preparation-cache ablation and portfolio outcome."""
import json,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(root):
    c=read(root/'contract.json');errors=[];pairs=[];jobs=[]
    for q in [2,3]:
        arms={}
        for arm in ['base','prepared']:
            name=f'q{q}_072_{arm}';p=root/'jobs'/name;r=read(root/'rows'/(name+'.json'));s=r['summary'];d=read(p/'details.json')
            a=s['arguments'];valid=s['valid'] and s['complete'] and not s['error'] and not s['deadline_stop'] and s['worker_exitcode']==0 and r['returncode']==0
            if not valid or r['wall']>600:errors.append(name+': verification/time failure')
            if not a['reuse'] or bool(a.get('ordering_prepare'))!=(arm=='prepared') or any(a[k]!=c[k] for k in ['cores','seconds','seed','max_proposals']):errors.append(name+': argument mismatch')
            score=read(p/'scored.json');hashes={}
            for x in score:
                if x['plan_sha256'] in hashes and hashes[x['plan_sha256']]!=x['result_sha256']:errors.append(name+': repeated score mismatch')
                hashes[x['plan_sha256']]=x['result_sha256']
            search=read(p/'search/search.json')
            row=dict(problem=q,arm=arm,valid=valid,makespan=s['makespan'],added=s['added'],seconds=r['wall'],verify_seconds=d['final_verify_seconds'],rss_mib=s['peak_child_rss_bytes']/1024**2,scored=len(score),stats=d['generation_stats'],counts=search.get('family_counts',search.get('counts',{})))
            jobs.append(row);arms[arm]=(row,hashes,d)
        a,ha,da=arms['base'];b,hb,db=arms['prepared'];shared=ha.keys()&hb.keys()
        if any(ha[h]!=hb[h] for h in shared):errors.append(f'Q{q}: shared result mismatch')
        if any(da[k]!=db[k] for k in ['input_sha256','provenance']):errors.append(f'Q{q}: input mismatch')
        pairs.append(dict(problem=q,case=72,base=a['makespan'],prepared=b['makespan'],cycle_reduction=a['makespan']-b['makespan'],cycle_increase_pct=100*(b['makespan']/a['makespan']-1),added_delta=b['added']-a['added'],shared=len(shared),base_scored=a['scored'],prepared_scored=b['scored']))
    micro=read(root/'summary.json');ablation=read(root/'ablation/summary.json');stress=read(root/'stress/summary.json')
    for folder in [root,root/'ablation',root/'stress']:
        r=read(folder/'results.json');seen={}
        for row in r['rows']:
            if row['case'] in seen and seen[row['case']]!=row['hashes']:errors.append(str(folder)+': candidate mismatch')
            seen[row['case']]=row['hashes']
    result=dict(errors=errors,jobs=jobs,pairs=pairs,fixed_work=micro,ablation=ablation,stress=stress,formal_promoted=False)
    (root/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 排序内部不变准备复用验证','',
        '冻结提交版不变。新增实验OrderingPreparation：缓存划分对应的依赖结构、排序后的后继、关键路径rank和张量(i,size,tier)表；核心归属、live/resident、remaining counts和ready heap逐次重建。保持评分算术及平局规则，完整官方全局评价不复用。',
        '两臂均开启上一轮GenerationReuse；新臂额外采用预整理数据与准备缓存。缓存仅在同一不可变图作用域有效，完整有序mapping作键，序列化负载预算32MiB；RSS另测。',
        '', '## 固定工作量与消融','',
        '033/067/072分别有3465/8804/29666个操作，所用初解仅7/552/6个子图。每臂8个不同排序参数组合、3次交替顺序重复。表中为中位数，不能代表全求解耗时或NPU周期。',
        '', '|case|原排序 s|预整理但不缓存 s|预整理并复用 s|后两者的增量耗时下降|','|---|---:|---:|---:|---:|']
    for x in ablation:lines.append(f'|{x["case"]:03}|{x["base_median"]:.6f}|{x["uncached_median"]:.6f}|{x["prepared_median"]:.6f}|{x["reuse_only_pct"]:.2f}%|')
    lines+=['','case072另以29666个单操作子图压力测试，每臂4个变体、2次重复，只验证排序等价与耗时，不把该压力划分当作官方提交方案。','', '```json',json.dumps(stress,indent=2),'```','',
        '初始双臂固定工作量测得22.92%/26.39%/34.40%的整体排序耗时下降，但三臂消融说明其中一部分来自循环避免重复张量拆解；不能全归因于跨调用缓存。短计时存在噪声，不宣称统计显著性。',
        '', '## 完整组合590秒验证','',
        'Q2 protected与Q3 combined各做case072五核一对，两臂96提议、种子0，20%预算留最终原版重放与物理审计。暖初解历史生成不计。',
        '', '|问题|原周期|新周期|下降 cycles|额外搬运变化 bytes|评分次数|','|---|---:|---:|---:|---:|---:|']
    for x in pairs:lines.append(f'|Q{x["problem"]}|{x["base"]:,}|{x["prepared"]:,}|{x["cycle_reduction"]:+,}|{x["added_delta"]:+,}|{x["base_scored"]}→{x["prepared_scored"]}|')
    lines+=['',f'检查问题{len(errors)}；共同方案完整结果哈希核对{sum(x["shared"] for x in pairs)}；完整复核{sum(x["valid"] for x in jobs)}/4。',
        f'最长外部耗时{max(x["seconds"] for x in jobs):.3f}秒，峰值子进程RSS{max(x["rss_mib"] for x in jobs):.2f}MiB。',
        '', '## 使用边界','',
        '不替换冻结提交版，不更新100图或1～5核正式成绩。原protected/combined代码保持不变。计时驱动的自适应顺序可能分叉，因此检查共同方案而不要求全程前缀相同。',
        '复跑完整组合按rows/*.json.command，在新输出目录执行；固定工作量脚本为程序/q23_order_prepare_bench.py、ablation.py、stress.py对应文件，均需新目录。汇总：python 程序/q23_order_prepare_report.py 图表/runs/20260925-A-q23-order-prepare。','']
    lines+=['## 本轮结论与归因','',
        'Q2/072周期增加27041（约0.567%），额外搬运增加7354256字节；Q3/072持平。不将实验推广到冻结提交版。',
        'Q2准备缓存51次调用命中44次。两臂都先找到4811152周期方案；基线随后由order候选改善到4768866，新臂由packing候选到4795907。基线的最终方案未进入新臂评分池。',
        '实际时间决定保护窗口和收益/耗时权重，复用改变了搜索路径：joint 5→7，packing 2→7，frontier 3→1；评分25→29仍无法弥补遗漏候选。这是搜索预算机会成本，不能把更快的排序等同更优方案。',
        '下一轮应先固定基础候选次序，避免瞬时耗时变化挤掉已有效机会，再让节省时间用于追加搜索；需另做同预算对照。本轮不修改自适应策略来掩盖负结果。','']
    (root/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return result

if __name__=='__main__':
    r=report(Path(sys.argv[1]));print(json.dumps(r['pairs'],indent=2));print(r['errors'])
    if r['errors']:raise SystemExit(1)
