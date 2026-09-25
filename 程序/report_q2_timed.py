"""Summarize this development round without changing the official 100-case score."""
import csv,json,statistics
from pathlib import Path
from q1_io import ROOT,write_json,sha


def main():
    base=ROOT/'图表/runs'
    paths=[base/'20260925-A-q2-timed-paired-v2',base/'20260925-A-q2-protected-pilot',
           base/'20260925-A-q2-protected-confirmation']
    results=[]
    text=['# 问题二五核限时算法组合实验（研发证据）','',
          '正式100图五核平均加速比仍为4.159974。本轮小样本没有替换正式500组结果。', '',
          '## 方法与计时', '',
          '继承原场景B模型：同核子图组成核内Task并保留数据复用，跨核COPY释放延迟、共享DDR竞争、四Pipe依赖和缓存容量均由原版官方评估器决定。目标按Makespan、额外搬运量依次比较。', '',
          '新入口 q2_timed_portfolio.py 提供通信权重重映射、拓扑粒度、生命周期排序、迁移/拆分/边界修复和合法空隙插入。protected进一步保留旧局部搜索的前32次提议（至多占剩余时间40%），再混合分量向量装箱和通信前沿划分。结构规则使用图特征，不读取case编号或既有答案。', '',
          '每次完整原版官方评估都计入时间；只保留官方已接受的不可变计划/结果文件，以原子指针发布回退方案。父进程实施硬超时，默认590秒，清理进程预留余量。首次合法评价未完成则明确失败，不输出虚构成绩。候选最多96次提议，非组合穷举。', '',
          '配对使用相同预生成Q1种子、seed=0、60秒上限，baseline只运行原有候选及普通J，ordinary_extended在同上限内增加旧局部搜索，portfolio/protected使用组合。基线可能提前结束，不能宣称每臂实际用时完全相等。固定单核分母和独立验收回放不计入求解，导入种子的生成不计入，因此这些为暖启动实验。无migration入口为冷启动分量方案，不能把暖启动性能当作冷启动证明。', '',
          '自适应分配包含实测秒数；同随机种子也可能因主机负载不同产生不同搜索路径。case039另验种子1、2，但没有完成全验证集多种子统计，不能声称统计显著。', '']
    for folder in paths:
        if not (folder/'rows.json').exists():continue
        rows=json.loads((folder/'rows.json').read_text(encoding='utf-8'))
        contract=json.loads((folder/'contract.json').read_text(encoding='utf-8'))
        text += ['## '+folder.name,'','|case|方法|原版周期|新周期|周期下降|加速比|额外搬运字节|求解秒数|',
                 '|---|---|---:|---:|---:|---:|---:|---:|']
        for r in rows:
            if r['status']=='ok':
                text.append(f"|{r['case']:03}|{r['arm']}|{r['old_makespan']}|{r['makespan']}|{100*(1-r['makespan']/r['old_makespan']):.4f}%|{r['speedup']:.6f}|{r['bytes']}|{r['seconds']:.3f}|")
        summaries={}
        for arm in contract['arms']:
            rs=[r for r in rows if r['arm']==arm and r['status']=='ok']
            summaries[arm]=dict(count=len(rs),expected=len(contract['cases']),
                mean_speedup=statistics.mean(r['speedup'] for r in rs) if rs else None,
                total_cycles=sum(r['makespan'] for r in rs),total_bytes=sum(r['bytes'] for r in rs),
                wins=sum(r['makespan']<r['old_makespan'] for r in rs),
                ties=sum(r['makespan']==r['old_makespan'] for r in rs),
                losses=sum(r['makespan']>r['old_makespan'] for r in rs))
        text+=['','```json',json.dumps(summaries,ensure_ascii=False,indent=2),'```','']
        results.append(dict(run=folder.name,summaries=summaries,rows=rows,
            contract_sha256=sha((folder/'contract.json').read_bytes())))
    with (base/'20260924-A-q2-full-r07-shared-r08/pairs.csv').open(encoding='utf-8-sig') as f:
        baseline={int(r['case']):r for r in csv.DictReader(f) if r['cores']=='5'}
    protected=[r for batch in results for r in batch.get('rows',[]) if r['arm']=='protected' and r['status']=='ok']
    if len(protected)==9:
        old_cycles=sum(r['old_makespan'] for r in protected);new_cycles=sum(r['makespan'] for r in protected)
        old_bytes=sum(int(baseline[r['case']]['r07_bytes']) for r in protected);new_bytes=sum(r['bytes'] for r in protected)
        combined=dict(cases=[r['case'] for r in protected],old_mean_speedup=statistics.mean(r['single']/r['old_makespan'] for r in protected),
            new_mean_speedup=statistics.mean(r['speedup'] for r in protected),old_cycles=old_cycles,new_cycles=new_cycles,
            cycles_reduction=1-new_cycles/old_cycles,old_bytes=old_bytes,new_bytes=new_bytes,bytes_reduction=1-new_bytes/old_bytes,
            scope='same protected method on 9 development/confirmation graphs, NOT full100')
        text+=['## 统一protected规则的九图汇总','','```json',json.dumps(combined,ensure_ascii=False,indent=2),'```','']
        results.append(dict(run='protected_nine_graph_summary',summary=combined))
    large=base/'20260925-A-q2-timed-large/validation.json'
    if large.exists():
        data=json.loads(large.read_text(encoding='utf-8'));text+=['## 大图压力测试：第一版portfolio，非protected','',
            '|case|原周期|新周期|周期下降|额外搬运变化|求解秒数|独立官方重放|',
            '|---|---:|---:|---:|---:|---:|---|']
        for r in data:
            old=baseline[r['case']]
            text.append(f"|{r['case']:03}|{old['r07']}|{r['makespan']}|{100*(1-r['makespan']/int(old['r07'])):.4f}%|{100*(r['bytes']/int(old['r07_bytes'])-1):+.4f}%|{r['seconds']:.3f}|{r['replay_equal']}|")
        text+=['','服务器独立冻结目录运行，两个并发，与正在运行的Q1批次不重复。包SHA256：f4f7cfcc6e1707e7f7e6dec292dbb2e9f3e13ed26414681d3739288ad6386ecf；源码对应提交2d1dbd67。大图结果不可与protected的逐图最佳值拼成一个正式算法成绩。','']
        results.append(dict(run='large_first_portfolio',rows=data))
    checks=base/'20260925-A-q2-timed-report/extra_validation.json'
    if checks.exists():
        data=json.loads(checks.read_text(encoding='utf-8'))
        text+=['## 冷启动与种子检查','','```json',json.dumps(data,ensure_ascii=False,indent=2),'```','']
        results.append(dict(run='cold_and_seed_checks',rows=data))
    text+=['## 审查与限制','',
        '同核复用、每消费核心去重COPY、跨核释放、直接依赖边、容量及生命周期的既有8项测试，加上新候选合法性、冷启动官方重放和超时失败关闭3项测试均通过。逐实验最终方案另外重新调用原版官方评估，序列化后逐字段完全相同。', '',
        '首轮独立回放比较曾因JSON把整数键转为字符串产生断言失败，未计入成绩；已改为序列化归一后完整字段比较，失败目录保留。小样本存在搬运上升；周期微降不等于搬运一定减少。尚无全量新均值、跨平台同预算对照或严格最优性保证。', '',
        '正式阶段门禁NOT_RUN。本轮为Q2研发扩展，不宣称Q1/Q2/Q3交付已重新验收。']
    out=base/'20260925-A-q2-timed-report';out.mkdir(exist_ok=True)
    (out/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    write_json(out/'evidence.json',dict(official_five_core_mean_speedup=4.159974,experiments=results))
    print(out)


if __name__=='__main__': main()
