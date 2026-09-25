"""Audit protected prefixes and report cache CPU time separately from makespan."""
import json,gzip,sys
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def report(root):
    old=root/'20260925-A-q23-diagnostics';r2=root/'20260925-A-q23-preserved-r2';p=root/'20260925-A-q23-preserved-r2b'
    c=read(p/'contract.json');out={'pairs':[],'cache':{},'checks':[],'promote_full100':False}
    lines=['# 完整基础序列、候选回填与低复制准备缓存','',
        '本轮保持上一轮16个基础候选的完整顺序。完成后先做原版重放和物理内存检查并保存base_complete，再生成至多8个补充候选。补充候选与基础候选去重，空缺由后续基础候选回填，至多24个候选。所有诊断和复核计入90秒暖启动预算。',
        '这里的“完整基础序列”明确指上一轮最多16个候选，不是保护任何长度的无限搜索。对照组同预算继续普通搜索至最多24个，因此新组合仍可能因后8个名额的分配而逊于对照。',
        'r2先验证候选规则；r2b再增加两臂一致的基础阶段复核检查点并重跑20项。r2缓存微基准与r2b求解分开运行，缓存实现未改变。','',
        '| 问题/case | 旧16候选对照周期 | 新24上限对照周期 | 新组合周期 | 新组合评分数 |',
        '|---|---:|---:|---:|---:|']
    times=[]
    for q in [2,3]:
        for i in c[f'q{q}_cases']:
            a=read(p/f'trials/q{q}_{i:03}_control/summary.json');b=read(p/f'trials/q{q}_{i:03}_guided/summary.json')
            d=read(p/f'trials/q{q}_{i:03}_guided/details.json');prev=read(old/f'trials/q{q}_{i:03}_control/summary.json')
            oldkeys=[x['sha256'] for x in read(old/f'trials/q{q}_{i:03}_control/pool.json')['candidates']]
            assert d['protected_keys']==oldkeys and d['prefix_complete']
            for arm in ['control','guided']:
                folder=p/f'trials/q{q}_{i:03}_{arm}';s=read(folder/'summary.json');detail=read(folder/'details.json')
                assert s['valid'] and s['complete'] and not s['error'] and s['total_seconds']<=90
                with gzip.open(folder/'base_complete.evaluation.json.gz','rt',encoding='utf-8') as f:base=json.load(f)
                assert (s['makespan'],s['added']) <= (base['makespan'],base['data_movement_bytes']['added_copy_bytes'])
                times.append(s['total_seconds'])
            assert b['makespan']<=prev['makespan']
            out['pairs'].append(dict(problem=q,case=i,old_base16=prev['makespan'],control=a['makespan'],guided=b['makespan'],protected_count=len(oldkeys),guided_count=len(d['evaluations'])))
            lines.append(f"| Q{q}/{i:03} | {prev['makespan']} | {a['makespan']} | {b['makespan']} | {len(d['evaluations'])} |")
    lines+=['','所有10组新组合均保留旧16候选对照的成绩，case033的基础收益已恢复。相对新24上限对照：Q2六组全平，Q3三平一负（044：35975对35703）。这仍不支持默认推广关键候选；优先保留普通搜索，新候选只作实验补充。','',
        '## 复制开销修正','',
        '旧实现miss时先deepcopy再序列化测量大小，hit再次deepcopy。新SerializedPreparationReuse在miss时直接保存不可变pickle字节，hit反序列化得到独立对象；不共享可变字典，也不读取外部pickle。仍使用完整有序输入和配置作为键，每次重新模拟全局DDR、依赖及L2/FIFO。',
        '微基准使用每图8个不同方案，三次轮换原版/旧复制/新快照的执行次序。冷流包含真实候选间的核内准备复用，没有重复完整方案；暖重复池另列，不混为生产命中率。时间含结果比较，三种模式口径一致。','',
        '| 图 | 冷流新快照相对原版耗时 | 冷流新快照相对旧复制耗时 | 完整字段一致次数 |',
        '|---|---:|---:|---:|']
    for f in sorted((r2/'trials').glob('*/reuse_benchmark.json')):
        x=read(f);rs=x['rows'];stat={phase:{m:sum(r['seconds'] for r in rs if r['phase']==phase and r['mode']==m) for m in ['original','deepcopy','serialized']} for phase in ['cold_distinct','warm_repeat']}
        cold=stat['cold_distinct'];count=sum(r['equal_count'] for r in rs if r['mode']!='original')
        assert all(r['all_equal'] for r in rs)
        out['cache'][f.parent.name]=dict(times=stat,checked=count,vs_original_percent=(cold['serialized']/cold['original']-1)*100,vs_deepcopy_percent=(cold['serialized']/cold['deepcopy']-1)*100)
        v=out['cache'][f.parent.name]
        lines.append(f"| {f.parent.name} | {v['vs_original_percent']:+.2f}% | {v['vs_deepcopy_percent']:+.2f}% | {count} |")
    out['max_total_seconds']=max(times);out['validated_trials']=len(times);out['checks']=['all old base prefixes exact','base checkpoint exists and final lexicographically no worse','all final original replay and memory audit complete','Q3 FIFO audit complete']
    lines+=['',f'最终版本20项全部通过原版复核/物理内存检查，最长含复核耗时{max(times):.3f}秒。Q3另核验FIFO。r2+ r2b共40项小试验，均保留。',
        '缓存收益是求解器CPU评价耗时变化，不是NPU任务周期下降；四张历史图不代表全部大图。搜索对照中尚未启用缓存，以免混淆候选机制收益；不自动更换默认提交入口或全量成绩。',
        '固定T1及初始方案生成不计入本轮90秒，不能声称100图冷启动10分钟。正式阶段门禁NOT_RUN，未启动新100图批次。']
    (p/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(p/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return out

if __name__=='__main__':print(json.dumps(report(Path(sys.argv[1])),ensure_ascii=False))
