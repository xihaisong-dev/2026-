# 交接：Q23-FREEZE-SELECTIVE — 冻结提交候选与独立复用试验

## 交付信息

- A提交，接收后续A；2026-09-25（+08:00）；READY，仅指冻结与本轮试验完成。
- 提交候选分支：codex/q23-submit-freeze，提交ebce54dd；冻结清单图表/runs/20260925-A-q23-submit-freeze/freeze.json。
- 实验分支：codex/q23-generation-reuse，产物提交14f475cf71f60d2fac33b17c566e73b024981e37；未推送，无新PR或Issue。
- 输入为上一轮b7594a64；本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript；没有启动或冒充B/C。
- 正式阶段门禁NOT_RUN，未更新状态源。提交冻结不代表交付验收通过。

## 冻结内容

Q2 protected、Q3 combined保持原来的普通搜索保护、结构候选与官方择优规则，保留五核100图证据：平均加速比4.229586642/4.343254303。1397文件的源码、输入、种子与日志哈希已记录。两问正式模型和组合搜索源码在实验结束后再次校验未变。

仍需提交补齐：最新组合2～4核覆盖、必要初解生成与最终复核的端到端计时、最终提交数据与Q3同方案双配置附录。现有正式入口和旧500配置未覆盖。补齐提交应从冻结分支独立工作，不能直接从实验HEAD称为已冻结正式算法。

## 本轮实验

新增程序/q23_selective_reuse.py：

- GenerationReuse只记忆不可变图作用域内确定性的context/order_plan/proxy；完整有序参数哈希，返回隔离副本，32MiB序列化负载上限。外层提议继续消耗同样随机数，保留候选顺序，不缓存随机proposal，也不缓存全局时间。
- SelectivePreparationReuse将32MiB按三个阶段分额，二次访问才准入，大对象旁路，128探测零命中则本轮停止该阶段缓存。完整输入键与每次全局DDR/L2重算不变。
- 程序/q23_cache_search.py增加两个默认关闭的实验开关，仍保留最终原版重放、物理审计、检查点与20%复核预留。未增加候选或改进复核预留公式。

Q2选033/072、Q3选005/072，四臂base/generation/preparation/both，共16项；小图90秒、大图180秒、5核、种子0、96提议上限。服务器12并发，全部结束。16项最终原版重放及内存审计通过；263共同候选前缀、164评分完整哈希比较一致。

仅生成复用的共同前缀生成耗时下降63.28%、38.30%、36.53%、43.81%。只有Q2/033最终少16周期、多6144字节，其余周期和搬运持平；双开没有进一步周期收益。072选择性准备缓存仍0命中，本轮零淘汰且大部分键首次出现，不能把旧零命中全归因于容量。

结论：生成复用值得进一步验证；准备缓存保留实验开关，不推广、不启动新100图，不改变提交冻结。以上是暖启动短试验，不是统计显著性、全量成绩或十分钟冷启动证明。180秒的大图只有4～5次评分，长搜索稳态未测。

## 证据和复现

报告及所有产物：图表/runs/20260925-A-q23-selective-reuse/README.md、report.json、contract.json、jobs、rows、hashes.json、local_tests.json、validation.json。

服务器独立根目录/home/xihs/q1-campaigns/20260925-q23-selective；使用Python3.12.14。实际启动命令：

```sh
nohup /home/xihs/q1-runtime/run-python -u run_selective.py > selective.log 2>&1 < /dev/null &
```

run_selective.py与selective.log归档在实验目录。重跑必须用新副本、只保留合同而不保留旧jobs/rows；依赖项目官方输入、Q2初解以及上一轮Q3种子目录。不要覆盖既有证据。

本机实际验证退出码均0：

```sh
python -m unittest discover -s 程序/tests -p test_q23_selective_reuse.py -v
python -m unittest discover -s 程序/tests -p test_q23_cache_search.py -v
python -m unittest discover -s 程序/tests -p test_q23_cache_deadline.py -v
python -m unittest discover -s 程序/tests -p test_q23_preparation_reuse.py -v
python 程序/q23_selective_report.py 图表/runs/20260925-A-q23-selective-reuse
```

本机11项通过，服务器新增3项通过。181原始产物的下载与Git索引哈希均通过；.gitattributes保持原始字节。最小产物校验通过，正式门禁仍NOT_RUN。

## 接手操作与限制

提交补齐使用codex/q23-submit-freeze；实验后续使用codex/q23-generation-reuse。若继续实验，先对生成复用做更长预算和未参与调参图的对照，重点验证省下的时间是否带来最终周期收益，再考虑接入protected/combined完整组合。当前控制变量搜索是普通joint，不能冒充完整组合已验证。

缓存仅适用于同一不变图作用域；若修改图对象，必须重建上下文。两种软件缓存各32MiB，双开总负载上限64MiB，RSS另测。并发共享服务器墙钟有噪声，不宣称稳定百分比提速。没有修改模型目标、官方评估器或硬件L2配置。

无待批准阻塞；由接收人填写验收结论，不代填ACCEPTED。
