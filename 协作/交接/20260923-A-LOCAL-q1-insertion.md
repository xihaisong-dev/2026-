# 交接：LOCAL-q1-insertion — 插入式调度与通信优先级

## 交付信息

- 用户任务：更新 GitHub 代码和结果后继续文献启发优化。提交人 A 端 Codex；接收人仓库负责人/非作者审阅者，待指定。
- 日期：2026-09-23 +08:00；状态 READY（原型技术交接）。无独立 Issue。
- 分支 codex/q1-insertion-scheduling；PR 基于 codex/q1-literature-ablation。
- 产物 SHA：02e41ce14881f8bea466fefe8188fbce170fc477；输入提交 96be1dc。
- 本机目录：C:/Users/Lenovo/Desktop/华为杯-数模/2026华为杯数学建模。
- 输入：已审计 processed/q1；原附件 SHA256 3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9。无新增原始输入。
- 正式阶段维持 DISCOVERY / ready，无门禁批准，不作为 B/C 正式派稿。

## 产物与复现

- 程序/q1_insertion.py：独立实现满足双侧同核等待的空隙插入，通信等待 rank 可独立开启；新开关 insertion / comm_rank，旧默认行为不变。
- 程序/tests/test_q1_insertion.py：等待、兼容性、合法性、固定预算与确定性测试。
- 程序/q1_ablation_report.py：支持显式配对和不同算例集合，仍核验重复/冲突哈希及完整配对。
- 图表/runs/20260923-A-q1-v4-{insertion,medium,medium-seed1,heldout,analysis}：32次运行、完整压缩官方结果、源码快照/哈希、对照报告。精确目录及实际命令见计算结果.md第四轮。
- 程序/README.md、计算结果.md：HEFT/dagP/超图论文来源、适配范围、限制和运行命令。源码清单为程序/code_manifest.json。

环境 Python 3.10+ 标准库。仓库根运行 `python 程序/主程序.py prepare` 可重建输入。按计算结果.md第四轮的五条命令重跑时必须更换新输出目录；本轮实际五命令均退出0。

验证：`python -m unittest discover -s 程序/tests -v` 20项通过；`python 协作/工具/check_repository.py` 0 errors；`git diff --check` 通过；报告器源码/产物哈希、指标、预算校验通过。

## 结果、影响与下一步

- 每次12次官方调用含初解，共384次。组合相对 local_cost + critical 8组胜3/平5/负0，平均时间下降0.582%；case_034两个种子下降2.272%/2.143%。case_078新增验证图2/4核均持平。
- 仅四图，核数/种子不是完整笛卡尔积；不构成统计显著性或普遍收益证据。替换候选启发式无理论不退步保证。共享DDR最终由官方仿真决定。
- 检索后独立实现，未复制外部代码或加入依赖。算法运行期间未调参；报告器改为通用配对。旧结果与源码快照未改。
- 影响 A 后续求解和 B/C 将来引用的数值，当前没有正式章节需要返工。无新增正式决策门禁。
- 接收人下一步：独立核验本提交与报告，决定扩大到更多图/核数。人工验收、全量实验与正式阶段门禁 NOT_RUN。

## 接收确认

由接收人在独立 clone 验证后填写验收时间、证据和 ACCEPTED/CHANGES_REQUESTED；提交方不代填。
