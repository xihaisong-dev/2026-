# 交接：LOCAL-q1-initial-solver — 问题一初版代码

- 提交端：A / Codex；接收人：A 端真人操作者；状态：READY（仅代码原型）。
- 日期：2026-09-23（北京时间）。分支：codex/q1-initial-solver。
- 产物提交 SHA：4818fcca8b542358e187e454d7c1d2652637573b。
- 输入基线：a71715e，赛题原件归档分支 admin/LOCAL-npu-problem-files；本任务基于该分支，依赖其原始附件。
- 未创建或启动 B/C。正式 DISCOVERY、FORMULATION、COMPUTATION 门禁 NOT_RUN；唯一阶段状态未修改。

## 已交付

- `程序/主程序.py`、`q1_io.py`、`q1_solver.py`：无损导入、greedy / multilevel / alns 求解与官方评估。
- `程序/README.md`、`程序/code_manifest.json`：接口、命令、依赖、源码哈希和局限。
- `程序/tests/`：9 项语义/回归测试、最大图构造与合法性检查。
- `计算结果.md`、`图表/runs/20260923-A-q1-v1-smoke/`、`图表/runs/20260923-A-q1-v1-scale/`：实际验证及完整证据。
- 输入 ZIP 哈希：3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9。processed 不跟踪，可由 prepare 重建。

## 接手复现

环境：Python 3.10+，仅标准库。在仓库根目录执行：

```powershell
python 程序/主程序.py prepare
python -m unittest discover -s 程序/tests -v
python 程序/主程序.py solve --cases case_001 case_093 case_034 --cores 1 2 4 --method alns --budget 4 --seed 0
python 程序/tests/check_scale.py 图表/runs/local-q1-scale-recheck
python 协作/工具/check_repository.py
git diff --check
```

实际检查：100 图输入审计通过；9 项测试通过；3 图 × 3 核数官方仿真成功；最大图两种方案覆盖/依赖/核心顺序检查通过；仓库检查 0 errors。Git 暂存版本源码和 9 个方案 SHA-256 与清单一致。耗时允许变化，固定参数下方案和 cycles 应一致。

## 限制与后续

- 接口为官方 node_to_subgraph + core_schedules，时间 cycles，流量 bytes。未改变其他端文件接口。
- 结果为小样本原型验证，未完成 100 图 × 4 核数的全量评测，不能派发正式数值写作。
- 最大图完整事件仿真尝试耗时较长已停止，只交付其方案构造与合法性结果。旧调试及中断运行保留本地，不冒充最终证据。
- 建议下一步开展等预算三算法对比、参数扫描和瓶颈分析；正式阶段启动仍按既有 intake 要求处理。
- 接收结论、验收时间和实际检出 SHA：待接收人本人填写，提交方不代填。
