# 交接：20260924-A-Q1 — 内存路由、主导分量与收缩检查加速

## 交付信息

- 本地编号：20260924-A-Q1-memory-routing；无新增Issue。
- 提交人/接收人：A / 用户及后续A、B操作者。
- 交付时间：2026-09-24（+08:00）；状态READY，未代填人工验收。
- 分支：codex/q1-memory-routing；本地提交，未推送、未更新main。
- 产物SHA：7eea1361cc0244cf4f5c5cd518e5738ddbabe9a6
- 输入SHA：b69c237；唯一写入目录C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 正式阶段和人工门禁未推进；输入继承processed清单并已核验。

## 已完成与产物

| 路径 | 内容 | 用途 |
|---|---|---|
| 图表/runs/20260924-A-q1-memory-routing/diagnostics | 六图×四核固定候选池，共50次完整评分 | 观察真实溢出与候选质量 |
| 同目录validation/runs | memory、hybrid各20份，全部原版最终复核通过 | 同预算质量对照 |
| 同目录runtime | 091四核数等价检查及五核顺序配对 | 搜索耗时证据 |
| 同目录runtime-profile | 749个堆栈采样、原cProfile中断日志关联 | 定位重复全图成环检查 |
| 图表/runs/20260924-A-q1-memory-analysis-v2 | 汇总报告、逐例CSV、JSON | 写作和下一轮 |
| 程序/q1_memory_routes.py | 有界工作量分批与主导分量拓扑切分 | 可选试验配置 |
| 程序/q1_contraction.py | DAG收缩可达性检查及增量邻接更新 | 不改变搜索语义的可选加速 |

## 接手复现

- Python标准库求解；服务器3.12.14。本地90项测试通过。
- 原始实际命令与包哈希：memory-routing/execution_metadata.json、validation/execution.json、validation/launch.py。冻结包diagnostic.zip、validation.zip、runtime.zip均已核验。
- 搜索12机会，其中1次固定单核引用、11次完整评分，四种基础粒度保留。所有运行seed0，核数2～5。
- memory目标058/039/072，hybrid目标009/100/040；两者均加028/067作保护组。可复现整套命令在程序/README.md。
- 实际分析命令（退出0，重复时改为新output）：

```powershell
python 程序/q1_memory_report.py --runs 图表/runs/20260924-A-q1-memory-routing/validation/runs --baseline 图表/runs/20260924-A-q1-ranking-full100 --diagnostics 图表/runs/20260924-A-q1-memory-routing/diagnostics --runtime 图表/runs/20260924-A-q1-memory-routing/runtime --output 图表/runs/20260924-A-q1-memory-analysis-v2
python -m unittest discover -s 程序/tests -p "test_q1*.py"
```

- 预算：质量试验440次完整评分+40次引用+40次原版最终复核；离线候选诊断50次完整评分；运行优化6次完整搜索共66次评分+6次引用。运行优化输出与既有官方结果全字段相等，复用原版核验证据而不再额外做六次慢重放。原cProfile另有一次中断诊断，未完成持久化调用台账，不能纳入同预算算法收益；保留堆栈与中断日志，不冒充完整运行。
- 运行源码、冻结包、既有输入、官方结果、400基线引用均核查；627份新证据的暂存字节与落盘字节一致。
- 首次汇总保护一致性断言发现真实退步；保留memory-analysis/audit_finding.md。v2改为显式报告保护组退步，没有修改方案或试验数据。

## 结果、风险和后续

- memory目标12胜，合计时间−14.6173%、额外搬运−45.1633%；hybrid目标10胜2平，时间−20.7129%、额外搬运−81.2901%。仅定向开发样本，不是新100图成绩。
- memory的028四核退步0.16747%；候选13608312比当时11035873差，未被采用却占用预算，挤掉最后一次local_reschedule（10694242→10676362）。7份保护方案相同；hybrid的8份保护方案全部相同。
- memory不直接替换默认。下一步应验证候选机会成本保护/筛选，再扩大样本；不能按case白名单避免退步，也不能把离线最佳候选拼成算法成绩。
- component_fast是等价加速：091四核数搜索267.9/288.0/288.9/270.9秒，轨迹、方案、评价与历史完全相同。同机单worker五核493.7→167.2秒，观测2.952倍。仅一次配对、后台负载变化，不给统计置信承诺。
- 搜索秒数不包含固定单核冷计算和原版最终复核；新内存布局的原版最终复核也可能较慢，端到端10分钟仍未全面满足。
- 三个可选配置分开验证；没有验证全量组合，不将收益相乘。正式默认、main、论文数值不自动更新。
- 无接口变更，场景A同核跨Task仍需DDR；缓存和通信语义未放松。
- 服务器全部本轮任务结束，SSH关闭，无待运行任务。
- 接收人下一步：先读v2报告和028四核的两份search.json，再决定独立预算筛选验证；写作仅可引用当前定向试验范围。

## 接收确认（接收人填写并提交）

未填写，等待接收人核对产物SHA和证据。
