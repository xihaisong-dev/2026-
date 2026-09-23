# 交接：LOCAL-q1-lookahead-audit — 瓶颈前瞻、结构下界与审核复核

## 交付信息

- 任务：继续以官方总完成时间优化，核对用户提交的PR #4审核报告。
- 提交人 A 端 Codex；接收人仓库负责人/非作者审阅者待指定；2026-09-23 +08:00；READY（原型技术交接）。
- 分支 codex/q1-bottleneck-lookahead，基于 codex/q1-insertion-scheduling；输入提交 eacf0df。
- 产物 SHA：70ea36506862082d1c0452df90f95eb5d03f133b。
- 本机目录 C:/Users/Lenovo/Desktop/华为杯-数模/2026华为杯数学建模。
- 输入：已审计processed/q1，附件SHA256 3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9。审核文本由用户本轮提供；未获得审核方100用例原始结果文件。
- 阶段仍DISCOVERY / ready，无正式门禁批准，不派B/C正式章节。

## 产物与真实验证

- 程序/q1_lookahead.py、可选lookahead开关：至多12个主导Pipe拆分候选，按预测完成时间排序，官方评价决定成绩。
- 程序/q1_bounds.py、报告器--bounds：非COPY必需工作量与计算CP下界，不宣称可达。
- 程序/tests/test_q1_lookahead.py、test_q1_bounds.py；程序/code_manifest.json与README。
- 图表/runs/20260923-A-q1-v5-lookahead：16次运行、192次官方调用、完整源码快照/产物哈希；v5-analysis：配对与下界报告。
- 审查/问题一初版审核复核.md：逐项核查原始4818fcca，而非用新代码替旧代码辩护。
- 计算结果.md第五轮记录两个真实实验/汇总命令，均退出0。重跑须新目录，原目录不可覆盖。环境Python3.10+标准库，根目录运行，输入可由 `python 程序/主程序.py prepare` 重建。
- `python -m unittest discover -s 程序/tests -q`：24项通过；`python 协作/工具/check_repository.py`：0 errors；`git diff --check`通过。报告器核验预算、完整指标、输入/源码/产物哈希通过。

## 结论与限制

- 新策略同预算八组胜4/负4，平均时间下降1.204%；case_078种子0下降6.513%。保持旧默认，不能全局替代。
- 已观察最佳时间/保守下界1.121～1.660，不证明实际次优程度或可达到下界。跨种子/配置择优不冒充单次调用预算成绩。
- 审核关于等待未建模、迁移拓扑层级、非法提案占用官方调用次数等判断不成立；拒绝重复累加等待。采纳下界、成本精度和搜索范围改进。用户目标仍是makespan第一，不增加未经验证的bytes加权主目标。
- 未修改原件/官方程序/旧运行/正式状态。全量100图/全部核数/人工接收NOT_RUN。
- 下一步：接收人独立核验报告与原始代码证据；A进一步优化代理成本/候选选择，并扩大同预算样本。影响A求解和未来B/C结果引用；当前无正式章节需要改写。

## 接收确认

由接收人独立填写验收时间、证据、ACCEPTED/CHANGES_REQUESTED；A不代填。
