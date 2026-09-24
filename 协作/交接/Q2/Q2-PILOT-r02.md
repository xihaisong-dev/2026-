# 交接：Q2-PILOT-r02 — 当前 main 首轮建模与负结果

## 交付信息

- 本地编号：Q2-PILOT-r02；角色：A。
- 接收人：A后续研究；B/C尚未派稿，不代表正式写作证据冻结。
- 日期：2026-09-24 +08:00；状态：DRAFT。
- 分支：codex/q2-main-r02；产物SHA：未提交。输入main：50b91d46a7bd43ca404c1285dfc27929496bf266。
- 工作目录：C:/Users/Lenovo/.codex/worktrees/q2-main-r02/2026华为杯数学建模。
- 正式阶段：未推进，门禁 NOT_RUN；本轮是用户授权的研究原型。
- 来源及哈希：审查/证据/20260924-A-q2-main-r02/reading_sources.json、source_manifest.json；运行contract.json。

## 已完成与产物

| 路径 | 内容 | 下游用途 |
|---|---|---|
| 问题分析.md、建模报告.md | Q1→Q2规则差异、继承边界、B统一模型 | 后续研究依据 |
| 程序/q2_submit.py | 标准B计划输出、上下文隔离缓存 | 可复现实验入口 |
| 图表/runs/20260924-A-q2-main-r02/ | 56份方案/评价、28配对配置、五点曲线和耗时 | 负结果与反例 |
| 审查/问题二基于当前main的首轮验证_r02.md | 完整首轮验证报告 | 不支持引导J直接采用 |

## 接手复现

- Python 3.12标准库；先按程序/README.md准备官方processed输入并verify。
- 单图：`python 程序/q2_submit.py 数据/processed/q1/data/case_006.json -n 2 --migration 图表/runs/20260924-A-q1-delivery-r02/solutions/2cores/case_006_multicore_res.json --output output/q2-repro-new`
- 测试：`python -m unittest discover -s 程序/tests -p "test_q2*.py" -v`，实际退出0、11项通过，日志审查/证据/20260924-A-q2-main-r02/unit_tests.txt。
- 批量：q2_main_campaign.py freeze/development/validation/scale；不得覆盖已有OUT，复现时在隔离副本或版本化新OUT冻结；服务器大图使用q2_large_campaign.py，仅更换固定单核分母的等价计算引擎。
- 固定seed0，8基础+4修复机会，ordinary/guided各12；标准输出仅node_to_subgraph和core_schedules。完整最终B结果必须一致。

## 风险、接口和后续

- 引导J未过预设门槛，不升为默认，不运行百图，不将开发收益当独立结论。
- case048候选体系弱于参考B历史结果；下一轮先保护参考B HEFT候选，再同预算检验通信代理，不覆盖当前证据。
- 真实生命周期与队首阻塞只能作候选启发，局部指标下降而Makespan上升已有反例。L/合并/重划分仍未在本轮对照。
- Q1冻结源和成绩未改。新增Q2接口与报告，已有结果索引保留Q1原字段。无正式论文替换，无B/C自动启动。
- 接收确认：待接收人填写；本文件不代填验收结论。
