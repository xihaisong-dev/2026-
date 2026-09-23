# 交接：LOCAL-q1-literature-ablation — 文献启发的四开关与同预算消融

## 交付信息

- 任务：用户要求逐项实现局部成本、关键路径、局部粒度、多候选预算分配并做同预算消融；无独立 Issue。
- 提交人：A 端 Codex；接收人：仓库负责人/非作者审阅者，尚待指定。
- 日期：2026-09-23（+08:00）；状态：READY（原型技术交接，非正式论文派稿）。
- 分支：codex/q1-literature-ablation；Draft PR 以 codex/q1-refinement 为 base。
- 产物提交：906267f674d1e11bb0f305173f44ae57a9c60290。
- 本机目录：C:/Users/Lenovo/Desktop/华为杯-数模/2026华为杯数学建模。
- 输入提交：1d58daf；正式阶段维持 DISCOVERY / ready，未批准新门禁。
- 原始附件 SHA256：3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9；无新增原始数据。

## 产物

| 路径 | 内容及证据 | 用途 |
| --- | --- | --- |
| 程序/q1_experimental.py | 四个可独立开关的候选生成与搜索机制 | 原型求解 |
| 程序/q1_ablation.py、q1_ablation_report.py | 等调用预算实验与哈希核验/配对汇总 | 可复核比较 |
| 程序/tests/test_q1_experimental.py | 七项新增回归测试 | 正确性验证 |
| 图表/runs/20260923-A-q1-v3-ablation | 48 次运行，源码快照/输入及产物哈希 | 四开关消融 |
| 图表/runs/20260923-A-q1-v3-legacy-control | 6 次旧 ALNS 对照，同样每次 12 调用 | 区分共同驱动器贡献 |
| 图表/runs/20260923-A-q1-v3-analysis | report.md、comparison.json | 描述性结论 |
| 计算结果.md、程序/README.md、程序/code_manifest.json | 实际命令、限制、接口和源码清单 | 复现入口 |

## 接手复现

环境 Python 3.10+ 标准库，仓库根目录运行。先 `python 程序/主程序.py prepare` 导入/核验原始附件（本轮复用已审计数据）。

本轮真实命令及退出码：

```powershell
python 程序/q1_ablation.py --output 图表/runs/20260923-A-q1-v3-ablation
python 程序/q1_ablation.py --configs legacy_alns --output 图表/runs/20260923-A-q1-v3-legacy-control
python 程序/q1_ablation_report.py --runs 图表/runs/20260923-A-q1-v3-ablation 图表/runs/20260923-A-q1-v3-legacy-control --output 图表/runs/20260923-A-q1-v3-analysis
python -m unittest discover -s 程序/tests -v
python 协作/工具/check_repository.py
git diff --check
```

全部退出码 0。重跑必须换新输出目录，不覆盖旧运行。54 次运行、648 次官方调用，17 项测试通过，仓库检查 0 errors。预算检查与文件哈希核验通过；不等于竞赛验收。正式门禁、人工审核、全量实验 NOT_RUN。

## 限制、接口与后续

- 总调用预算 `--evaluation-budget` 包含兜底/初解；旧 `--budget` 含义不变。旧算法默认不变。影响 A 端后续求解与 B/C 未来结果引用；暂不派正式写作任务。
- 三图、4 核、两种子探索性结果。local_cost + critical 六组胜共同对照，平均时间下降 1.274%；不证明普遍收益。
- adaptive 加入该组合后五组退步，暂不推荐；portfolio 仅在当前组合小幅改善。不得把相对旧 ALNS 的全部收益归因于新增开关。
- 下一步由 A 在更多图与核数验证 local_cost + critical，并修正自适应粒度过度合并。接收人先独立检查哈希及配对汇总，再决定是否扩大试验。
- 最早实验驱动器尚无自动源码快照功能，已按其记录哈希保存精确快照；当前驱动器自动保存。算法源码在实验期间未修改。
- 无改动题面、官方代码、正式阶段状态或旧运行。未提交旧调试目录不属于本次有效证据。

## 接收确认

由接收人在独立 clone 验证后填写；提交方不代填 ACCEPTED。
