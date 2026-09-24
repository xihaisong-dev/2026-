"""Audit completed first Q2 pilot against frozen main, without promoting it."""
import csv,json,math,statistics,subprocess
from pathlib import Path
from q1_io import ROOT,sha,write_json,verify
from q2_main_campaign import OUT,summarize


def main():
    contract=json.loads((OUT/'contract.json').read_text(encoding='utf-8'))
    summaries={}
    for phase,count in [('development',12),('validation',12),('scale',4)]:
        summarize(phase);s=json.loads((OUT/phase/'summary.json').read_text(encoding='utf-8'))
        assert len(s['rows'])==count,(phase,len(s['rows']))
        summaries[phase]=s
    rawrows=[];invalid=0;migration_invalid=[];diagnoses=0
    for p in sorted(OUT.glob('*/*/*/*/row.json')):
        r=json.loads(p.read_text());stats=json.loads((p.parent/'search.json').read_text())
        assert r['replay_equal'] and r['slots']==12
        if r['migration_makespan'] is not None:assert r['makespan']<=r['migration_makespan']
        else:migration_invalid.append(str(p))
        if stats['diagnosis']:
            assert stats['diagnosis']['start_reconstruction_max_error']==0;diagnoses+=1
        invalid+=sum(t['status']=='invalid' for t in stats['evaluations']);rawrows.append(r)
    assert len(rawrows)==56
    with (ROOT/'图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv').open(encoding='utf-8-sig',newline='') as f:
        previous_fixed={x['case']:int(x['single_makespan']) for x in csv.DictReader(f)}
    # Audit fresh references only; this table is never used to score Q2 runs.
    assert all(x['reference']==previous_fixed[f"case_{x['case']:03}"] for x in rawrows)
    for rel,h in contract['q1_protected_hashes'].items():assert sha((ROOT/rel).read_bytes())==h
    verify()
    q1diff=subprocess.check_output(['git','diff','--name-only','HEAD','--','程序/q1_*.py','图表/runs/20260924-A-q1-delivery-r02'],cwd=ROOT,text=True).strip()
    assert not q1diff,q1diff
    lines=['# 当前 main 问题二首轮建模、实现与验证','',
           '基础提交：50b91d46a7bd43ca404c1285dfc27929496bf266；分支 codex/q2-main-r02。原目录旧 Q2 代码和运行记录未覆盖。Q1 冻结程序及成绩保持不变。正式状态未推进。',
           '', '## 先交付的四项内容','',
           '问题一→问题二差异表、模块复用审计和首轮协议已写入问题分析.md末尾“基于 Q1-WRITE-r02 的规则复核”；统一模型与约束写入建模报告.md末尾问题二章节。原题来自仓库docx，文本提取与来源哈希在审查/证据/20260924-A-q2-main-r02/。',
           '关键区别是按核心合并 Task、COPY 级500周期释放、同核跨子图驻留、消费核心去重，以及共享DDR与操作级FIFO/内存依赖共同作用。不能沿用 A 的 Task 清空、全边界DDR或100/1000等待。',
           '保留图处理、结构分组、合法性、去重和预算思想；B的成本及缓存身份重新建立。完整Q1迁移方案必须B复评，失败才用整图合法回退。主目标仍为周期，额外搬运独立报告；同周期少搬运是求解约定，不冒称题面强制词典序。',
           '', '## 实现和公平性','',
           '- q2_current.py：8基础机会（迁移、整图、6结构槽位），原方案留优；普通/诊断引导J各追加相同4机会。两组前8计划哈希逐一相同。无L、无重划分修复同时叠加。',
           '- q2_submit.py：标准两字段JSON输出，显式图、配置、核数、可选迁移计划。默认ordinary是首轮对照入口，不代表完成全量采用。',
           '- 评价缓存只在当前B上下文内，含输入/配置/官方版本/计划；容量2，隔离返回对象。命中仍计搜索机会。最终回放绕过缓存。',
           '- 开发006/048/050，验证012/039/072，均2–5核；大图014/091仅2/5核，未插值为五点曲线。seed0为确定性规则，没有通过换种子逐例择优。',
           '- 大图在服务器运行，初始检查20逻辑核、约93GB可用；最终3个独立case并行。072发现为31387操作后从本机迁移，已完成012/039保留。单次计时含并行负载影响，不作显著耗时优势声明。',
           '- 最初大图卡在原始固定单核分母的全图完成扫描，经中断栈确认；当时未产生B搜索行。执行补充协议仅使用Q1已验证的精确计数引擎重新计算单核分母，完整小图输出与原入口相同。没有复用A多核成绩或改B评估器。失败启动和中断日志保留。',
           '', '## 真实实验结果','']
    for phase,label in [('development','开发'),('validation','验证'),('scale','大图')]:
        s=summaries[phase];rs=s['rows']
        lines += [f'### {label}','',f"引导J相对普通J：{s['outcomes']}；几何平均变化 {(s['geomean_ratio']-1)*100:+.6f}%。",
                  '| 核数 | 普通 J 平均提速比 | 引导 J 平均提速比 |','|---|---:|---:|']
        for k in s['curves']['ordinary']:lines.append(f"| {k} | {s['curves']['ordinary'][k]:.6f} | {s['curves']['guided'][k]:.6f} |")
        lines += ['',f"额外搬运合计普通/引导：{sum(x['ordinary_bytes'] for x in rs)}/{sum(x['guided_bytes'] for x in rs)} bytes；搜索耗时合计 {sum(x['ordinary_seconds'] for x in rs):.3f}/{sum(x['guided_seconds'] for x in rs):.3f} 秒（不含单核生成和最终重放）。",'']
        lines += ['迁移/结构基线（搜索预算不同，仅展示可行起点，不作等预算因果消融）：','',
                  '| 核数 | Q1原计划经B复评 | 8机会结构基线 |','|---|---:|---:|','| 1 | 1.000000 | 1.000000 |']
        for k in sorted({x['cores'] for x in rs}):
            subset=[x for x in rs if x['cores']==k]
            migration=statistics.mean(x['ordinary_speedup']*x['ordinary']/x['migration'] for x in subset if x['migration'] is not None)
            base=statistics.mean(x['ordinary_speedup']*x['ordinary']/x['base'] for x in subset)
            lines.append(f'| {k} | {migration:.6f} | {base:.6f} |')
        lines.append('')
        for x in rs:
            if x['outcome']=='loss':lines.append(f"退步：case_{x['case']:03}，{x['cores']}核，{x['ordinary']}→{x['guided']} cycles。")
        lines.append('')
    lines += ['## 时间线与真实生命周期诊断','',
              '对048/5核、050/4核、012/3核两组最终方案补做只读诊断，另计12次官方核内准备，不回灌搜索。6份操作开始时刻重建误差均为0，按全局真实开始/结束时刻重建的物理张量实例峰值均未超容量，6份均无spill搬运。数据保存在posthoc_diagnostics.json。',
              '048引导J缩短980周期，但额外搬运从506738增至523122字节；两组一条实际关键链都含12000周期跨COPY同步间隔，最繁忙Pipe利用率约49%，并非单纯计算满载或溢出瓶颈。应优先检查划分边界和释放顺序。',
              '012引导J的最大队首阻塞机会由6196降到3457周期，额外搬运也少2048字节，但总周期反而增加800。这直接否定了“减少一个局部阻塞指标必然缩短总工期”的假设；新的关键链和DDR重叠必须由完整B评价判定。',
              '退步原因是有限预算内的候选选择，而非接受劣于保留基线的方案：012/3核共同基线19120，普通J的group21迁入核0候选达到18128；引导J只试group30/37/24/99，最好18928。050/4核引导4个候选均未改善，保留58032；普通J找到了57912。后续可检验混合名额，但不能把两组最佳事后合并冒称同预算结果。',
              '050/4核引导J增加120周期、2400字节；主导PIPE_V利用率约60%，存在通信同步与多Pipe等待交织。没有spill的样本不能解释为靠减少spill取得收益，也不能因此推广到全部图。',
              '关键链按前驱类别归类的操作时长是固定运行的解释标签，不是可相加的因果损失；并行DDR额外时长、不同队首阻塞区间同样不能相加当作可回收Makespan。','']
    passed=summaries['validation']['gate']
    lines += ['## 采用判断与当前缺口','',
              f"预设独立验证条件：{'通过' if passed else '未通过'}。本轮未运行百图，未替换Q1或Q2默认采用版。",
              '开发中case048的新B放置代理不如参考工程既有B方案，说明诊断J局部收益不能证明整个候选体系更好。参考工程历史CSV比较另存，仅作差距定位，预算不同不作公平算法胜负证明。下一轮应保护直接按B规则生成的参考HEFT候选，再将新的去重放置代理作为单独挑战者；不能让更精确的代理自动替换原有效候选。',
              '大图求解耗时与执行周期分开：精确单核引擎加速只降低求解耗时，不计作调度加速。所有优化采用必须同时经过核数均值、退步图、额外搬运、预算机会和大图稳定性检查。',
              '', '## 校验','',f'56份最终完整B回放一致，28组基础候选保护检查通过，{diagnoses}份操作级诊断重建零误差。搜索机会 {sum(x["slots"] for x in rawrows)}，实际搜索调用 {sum(x["official_calls"] for x in rawrows)}，缓存命中 {sum(x["hits"] for x in rawrows)}；失败候选 {invalid}；非法迁移 {len(migration_invalid)}。11项B语义/缓存/诊断测试通过，另2张图的完整固定单核引擎结果相同。',
              '独立分支内Q1代码与交付结果无差异，迁移计划哈希及全部输入/官方文件哈希再次通过。运行与源码版本见contract.json、reference_backend_addendum.json；每个组合保留计划、完整评价gzip和逐候选search.json。']
    p=ROOT/'审查/问题二基于当前main的首轮验证_r02.md'
    if p.exists():raise FileExistsError(p)
    p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    decision=dict(status='pilot_complete_not_full100',validation_gate=passed,main_commit=contract['main_commit'],q1_frozen_unchanged=True,
                  summaries=summaries,full100=False,final_replays=56,search_slots=sum(x['slots'] for x in rawrows),search_calls=sum(x['official_calls'] for x in rawrows),
                  evidence={str(f.relative_to(ROOT)):sha(f.read_bytes()) for f in [p,OUT/'contract.json',OUT/'reference_backend_addendum.json']})
    write_json(OUT/'decision.json',decision)
    print('Report complete',passed)


if __name__=='__main__':main()
