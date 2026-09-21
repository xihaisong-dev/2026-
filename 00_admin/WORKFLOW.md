# 阶段状态与冻结

workflow.json 是唯一阶段状态源。当前 INIT；题面、正式输入、规则、模板和知识库均未确认。中文 / LaTeX 为可修改预设。目录搭建阶段可正常协作，不要求比赛门禁通过。

阶段顺序：INIT → RULES_PROBLEM_FROZEN → RETRIEVAL_PASS → PROTOCOL_FROZEN → TOURNAMENT_PASS → MODEL_RESULTS_FROZEN → PAPER_FROZEN → ACCEPTED。

由 O 核对证据、写决策并更新 phase。工具 status 只读取，check --record 只记录门禁，freeze 只创建冻结清单，均不自动修改 phase。

## 输入登记

原始文件放 01_problem/original；input_manifest.json 记录相对路径、角色、数据类别、来源和 SHA-256；rules.json 记录当届来源、模板、AI 政策和提交要求；semantic_contract.json 记录题数、目标、单位及冲突。未知项不得写 PASS / VERIFIED。

Windows 可用 `Get-FileHash -Algorithm SHA256 -LiteralPath '01_problem/original/problem.pdf'` 计算哈希。

## 常用命令

仅在实际文件存在、内容完整且前置证据通过后执行；不能捏造空壳证据：

```bash
python -X utf8 tools/workflow_guard.py freeze --workspace . --stage problem --actor O --paths 00_admin/rules.json 00_admin/input_manifest.json 00_admin/semantic_contract.json 01_problem/PROBLEM_BRIEF.md
python -X utf8 tools/workflow_guard.py check --workspace . --gate rules-problem --record
python -X utf8 tools/workflow_guard.py check --workspace . --gate retrieval --record
python -X utf8 tools/workflow_guard.py check --workspace . --gate protocol --record
python -X utf8 tools/workflow_guard.py freeze --workspace . --stage tournament_protocol --actor O --paths 02_retrieval/retrieval_manifest.json 03_model/ANALYSIS_MODELING_REPORT.md 03_model/tournament_protocol.json
python -X utf8 tools/workflow_guard.py check --workspace . --gate tournament --record
python -X utf8 tools/workflow_guard.py freeze --workspace . --stage model_results --actor O --paths 03_model/ANALYSIS_MODELING_REPORT.md 03_model/tournament_protocol.json 04_code 05_results
python -X utf8 tools/workflow_guard.py check --workspace . --gate model-results --record
```

论文冻结显式列出实际入口、章节、图、文献和 PDF；用 verify-freeze --stage paper 检查漂移。最终 ACCEPTED 还需独立复现、真实编译、逐页检查、引用、匿名、提交和 AI 使用核验，不能凭仓库 CI 判断。

冻结后变更先写 DECISIONS，说明失效范围，再通过 --replace --change-request '决策编号及说明' 替换相应冻结，重跑下游检查。旧运行保留。

| 交付方向 | 最小内容 |
| --- | --- |
| M → E | 变量单位、公式、约束、输入输出、候选、指标、预算和失败规则 |
| E → M/W | 代码版本、命令、配置/种子、run-id、指标、源数据及局限 |
| W → O | 源码、文献、图表来源、PDF、编译命令和待核对项 |
| O → 全员 | 当前可用版本、未决问题、影响范围和下一阶段负责人 |
