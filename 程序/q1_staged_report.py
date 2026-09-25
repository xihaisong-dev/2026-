"""Summarize measured staged-search ablations without post-hoc case selection."""
import argparse,json,hashlib
from pathlib import Path
from q1_io import ROOT,write_json

def load(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    base=ROOT/'图表/runs';records=[]
    for batch in ['20260925-A-q1-staged-ablation','20260925-A-q1-staged-validation-v2']:
        rows=load(base/batch/'summary.json')
        for row in rows:
            run=row['run'];assert row['exitcode']==0 and run['complete'] and run['within_limit'] and not run['worker_error']
            records.append(dict(batch=batch,case=row['case'],method=row['method'],makespan=run['selected']['makespan'],
                added_bytes=run['selected']['added_copy_bytes'],seconds=run['wall_seconds']))
    big=[]
    for case,old in [(67,'20260925-A-q1-timed-large/case_067_5cores'),(72,'20260925-A-q1-timed-large-final/case_072_5cores')]:
        prev=load(base/old/'run.json')['selected']['makespan']
        run=load(base/f'20260925-A-q1-staged-{case:03}-v2/run.json')
        big.append(dict(case=case,previous=prev,current=run['selected']['makespan'],reduction_pct=100*(prev-run['selected']['makespan'])/prev,seconds=run['wall_seconds']))
    bench=load(base/'20260925-A-q1-staged-ablation/reuse_benchmark_v2.json')
    for row in bench['rows']:row['time_reduction_pct']=100*(row['plain_seconds']-row['cache_seconds'])/row['plain_seconds']
    write_json(a.output/'evidence.json',dict(formal_full100=False,ablation=records,big_same_cap_historical_comparison=big,cache_benchmark=bench))
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'程序').glob('q1_*.py')}
    write_json(a.output/'source_manifest.json',manifest)
    lines=['# Q1 核内复用、分阶段限时与结构/时间线引导试验','',
        '结论：实现四项机制并完成开发验证。Task缓存与计数器等价评估通过完整字段对照；缓存首次实现因深复制而变慢，第二版修正后固定候选池评估更快。分阶段限时解除072原搜索阻塞，官方周期改善。结构引导和时间线修复存在明确退步，不适合全部默认推广。原正式100图结果及 q1_submit 默认规则不变。','',
        '## 机制与正确性边界','',
        '1. Task复用键包含完整局部图、生成的COPY/张量编号、容量与带宽。改变边界会重新构造局部图。相同节点集合不一定可复用，COPY编号变化也不冒险复用。LRU有界。',
        '2. 使用经过源文件哈希锁定的 indexed-counter 全局事件模拟。每个候选都重新派生Task依赖、核心顺序、全局DDR共享过程。只复用核内准备，绝不复用旧全局Task持续时间。每次完整模拟均计为评分，不是免费代理。',
        '3. 第二版缓存仅复制Task顶层字典；已核查锁定官方代码只新增顶层元数据和全新pipe_cursor，内部准备图只读。测试验证重复评估、跨核重排、局部拆分、边界编号、输出修改隔离、带宽改变、非法顺序拒绝。',
        '4. 独立子进程划分保底、初始搜索、组合搜索、原版复核。达到阶段期限中断当前候选并保留已完整落盘的结果。第一次复核提前结束后可回收余量再搜索一轮；后续复核超时仍保留已核验方案。',
        '5. 结构特征为弱连通分量数量/最大分量比例、计算关键链工作量比例、张量字节/计算量。仅作为探索先验，不使用case编号或历史最优标签。收益/耗时反馈与基础探索同时保留。',
        '6. 时间线修复从最晚结束Task逆向追踪实际释放约束（依赖跨核等待与同核串行间隔），最多12个Task；提出有限边界合并、拆分或迁移插入候选，统一合法性检查并精确评分。未将时间线等待、DDR拖慢与Pipe空闲简单相加。','',
        '## 分项对照：每配置相同60秒上限、seed=0、5核','',
        'previous=上一轮限时算法；reuse_stage=复用+分阶段；structure=再加结构先验；full=再加时间线修复。前批开发图048/071与新验证017/055；缓存/余量修正后另测此前未调试的032/088。源码修订和批次不可混称一个冻结版本的全量成绩。','',
        '|批次|case|previous|reuse_stage|structure|full|','|---|---|---:|---:|---:|---:|']
    for batch in sorted({r['batch'] for r in records}):
        for c in sorted({r['case'] for r in records if r['batch']==batch}):
            rows={r['method']:r for r in records if r['batch']==batch and r['case']==c}
            lines.append(f"|{'r01' if batch.endswith('ablation') else 'r02'}|{c:03}|"+'|'.join(str(rows[m]['makespan']) for m in ['previous','reuse_stage','structure','full'])+'|')
    lines+=['','032上完整组合退步，088上结构单独开启退步；不能取每行最小值来宣称存在已验证的自动选择器。r02保守组合在两张新图上均改善，但样本不足以证明全量优势。','',
        '## 大图：同为590秒上限，比较历史上一轮结果','',
        '|case|上一轮限时周期|本轮完整组合周期|下降率（负号为退步）|本轮含复核秒数|','|---|---:|---:|---:|---:|']
    for r in big:lines.append(f"|{r['case']:03}|{r['previous']}|{r['current']}|{r['reduction_pct']:.6f}%|{r['seconds']:.3f}|")
    lean=load(base/'20260925-A-q1-staged-067-reuse/run.json')
    lines+=['',f"067追加保守组合得到 {lean['selected']['makespan']} cycles、{lean['wall_seconds']:.3f}秒，优于本轮完整组合，但仍未超过上一轮13292569；保留负结果。072相对原正式基线4830220下降 {100*(4830220-big[1]['current'])/4830220:.6f}%。",'',
        '大图比较是同上限的历史对照，不是同一时刻相同机器负载的严格计时实验。搜索时间、候选数量和软件版本均可影响结果；只报告实际得到的方案质量。','',
        '## 固定候选池的复用开销','',
        '从五图此前保存的方案各取最多四个，按同一顺序评分两遍；共36次评分。重复第二遍用于检查复用潜力，不能当作正常搜索必然具有的命中率。与无缓存计数器后端逐字段一致，也与保存的原版结果一致；每图最后一个方案另作新鲜原版重放。单次短耗时测量，没有多次重复置信区间。','',
        '|case|无缓存秒|缓存秒|耗时下降|','|---|---:|---:|---:|']
    for r in bench['rows']:lines.append(f"|{r['case']:03}|{r['plain_seconds']:.3f}|{r['cache_seconds']:.3f}|{r['time_reduction_pct']:.2f}%|")
    lines+=['','## 验证和局限','',
        '- 5项Task缓存测试、2项结构/修复测试、3项原加速评估器回归及2项复核失败回退测试通过。24组小图对照全部正常完成且在时间上限内；最后提升方案必须通过原版完整字段复核。另有5份最终方案独立重放证据。',
        '- 限时单位为case×核数。固定整图单核计分基准无需每次搜索重算；本轮没有重算100图平均加速比。独立审计耗时与求解内复核分开记录。',
        '- 最终候选的原版复核耗时仍不可完全预测；超时只能退回已核验方案。bootstrap若超过自己的限额而无已验证方案，则明确失败，不宣称适用于所有图/所有硬件。',
        '- 分阶段会损失缓存跨进程复用；完整先验可能持续挤占更有效的邻域；固定缓存容量可能在碎任务图上抖动。当前不是最优性证明，也不是全量提交验收。',
        '- 本轮只比较5核，其他核数仅由既有基础回归覆盖，不可声称2～5核全量收益。正式全100同版本门禁 NOT_RUN。',
        '- r02原protocol的role文字误留r01案例编号；cases字段与实际目录始终为032/088，此处明确更正。未据r02结果修改其运行规则。','',
        '## 复现入口','',
        '```powershell',
        '# 当前完整组合（实验选项，未替换原提交入口）',
        'python 程序/q1_staged_portfolio.py 数据/processed/q1/data/case_072.json -n 5 --seconds 590 --output 图表/runs/reproduce-q1-staged-072',
        '# 保守组合：单独验证复用与限时',
        'python 程序/q1_staged_portfolio.py 数据/processed/q1/data/case_032.json -n 5 --seconds 60 --no-structure --no-timeline --output 图表/runs/reproduce-q1-staged-032',
        '# 只启用结构引导：添加 --no-timeline',
        'python 程序/q1_staged_experiment.py --cases 32 88 --cores 5 --seconds 60 --workers 2 --output 图表/runs/reproduce-q1-staged-ablation',
        '```','',
        'contract.json含源码摘要；candidate指针仅为加速评估候选，不能当已验证输出；verified指针和case_XXX_multicore_res.json才是最终官方核验方案。run.json含各阶段耗时、中断与错误，search/search2日志分别保留。固定种子在墙钟截止下不保证跨机器候选数量和最终方案一致，保存方案可以官方重放。']
    (a.output/'README.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
    print(json.dumps(dict(big=big,records=len(records)),ensure_ascii=False))

if __name__=='__main__':main()
