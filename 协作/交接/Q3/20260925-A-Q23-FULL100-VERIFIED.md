# 交接：Q23-FULL100-VERIFIED — 五核200配置运行中

## 交付信息

- A交后续A，2026-09-25 +08:00；DRAFT（计算进行中），无新Issue/PR，未推送。
- 分支codex/q23-full100-verified；启动产物提交df776a34；输入b1ed9f89。
- 本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 服务器xihs@120.27.220.233:9022，目录/home/xihs/q1-campaigns/20260925-q23-full100-verified，启动PID1773。密钥/密码不入库。
- 契约图表/runs/20260925-A-q23-full100-verified/contract.json；623源码/输入哈希，固定单核基准与200任务清单。官方输入manifest验证通过。

## 进行中与限制

用户要求启动Q2、Q3各100图五核计算。本轮Q2 protected、Q3 combined，生成复用开启；未推广新奖励权重与排序准备复用。每项590秒，种子0，384提议上限，20%预算留完整官方复核。15并发，按图规模降序、每图Q2/Q3相邻排队。

Q2固定Q1迁移初解，Q3固定最新Q2初解及旧Q3锚点，不读取本批Q2结果。384与早期96提议上限不同，不把差异归因于单个机制。历史初解和固定单核生成不计时，不宣称冷启动端到端十分钟满足。

启动时200项排队，15开始，0结束，无worker错误；这是静态快照，不能当作当前进度。服务器progress.json随完成更新。冻结提交版及正式成绩不变，正式门禁NOT_RUN。

## 已执行命令与接手

```sh
cd /home/xihs/q1-campaigns/20260925-q23-full100-verified
nohup /home/xihs/q1-runtime/run-python -u 程序/q23_full100_verified_run.py 图表/runs/20260925-A-q23-full100-verified > full100.log 2>&1 < /dev/null &
cat 图表/runs/20260925-A-q23-full100-verified/progress.json
tail -10 full100.log
```

服务器Python3.12.14、20逻辑核、启动可用内存约94GiB。启动器创建rows使用exist_ok=False，不可重复启动同一路径；不自动覆盖、重试失败项或拼入旧成绩。

结束标记complete.json，证据ZIP在图表/runs/20260925-A-q23-full100-verified-evidence.zip。取回后核对hashes.json和每项官方复核；分别汇总Q2/Q3所有100图的T1/T5算术平均、总周期、搬运和耗时。失败单列，缺图不得冒称全量。

Q3最终同方案无L2评估不在本启动器内；如果整理提交数据，需另加对应列并单列生成和核验耗时。此任务尚无新全量结果，不能交给写作人员作为已完成成绩。

## 验收状态

本机py_compile、200唯一任务与623文件哈希检查、git diff检查通过。官方全量结果验收NOT_RUN。接收者自行记录后续完成数与验收，不代填ACCEPTED。下一操作：读取服务器进度，完成后拉取归档，审核失败和统计口径。
