# 交接：LOCAL-q1-refinement

- 提交端 A / Codex，接收人 A 端真人操作者；2026-09-23 +08:00；状态 READY（原型改进）。
- 分支 codex/q1-refinement，基于 codex/q1-initial-solver / 6edd71f；依赖初版 PR #4。
- 产物提交：14d1b1930ab6eecc8c7d50e51a39609aa8b814a8。
- 新增 --refine-budget（默认 0），多粒度及真实 Task 时长引导的拆分/迁移候选，最终保留基础求解最优方案。官方输出接口和评估器未改变。
- 输入来源与哈希沿用初版，参见程序/code_manifest.json；无新增外部数据。

## 复现及实际验证

Python 3.10+ 标准库，在仓库根目录运行：

```powershell
python 程序/主程序.py prepare
python -m unittest discover -s 程序/tests -v
python 程序/主程序.py solve --cases case_001 case_093 case_034 --cores 2 4 --budget 4 --refine-budget 8
python 程序/主程序.py solve --cases case_001 case_093 case_034 --cores 2 4 --budget 12 --refine-budget 0
python 协作/工具/check_repository.py
git diff --check
```

10 项测试通过；官方评估次数逐组合相等。六个组合新策略胜出四个，另外两个纯随机 ALNS 更好。完整数据、运行耗时和源码哈希位于图表/runs/20260923-A-q1-v2-refine 与 20260923-A-q1-v2-equal-budget-control；解释见计算结果.md。仓库检查 0 errors。

## 限制与下一步

- 单种子三图对照，不是全量性能结论，不能替代正式对擂。可选优化增加评估成本，默认不改变原算法。
- 正式阶段状态未改动，门禁 NOT_RUN。未派发 B/C，未改写初版运行。
- 下一步：扩大图类型、核数和随机种子覆盖，研究自动分配粒度探索与 ALNS 预算。
- 接收人验收时间、实际 SHA 和结论：待本人填写，提交方不代填。
