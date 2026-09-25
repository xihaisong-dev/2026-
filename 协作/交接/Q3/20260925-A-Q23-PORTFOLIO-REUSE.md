# 交接：Q23-PORTFOLIO-REUSE — 完整组合生成复用验证

## 交付信息

- 本地编号Q23-PORTFOLIO-REUSE；A交付后续A；2026-09-25（+08:00）；READY仅表示本轮验证完成，接收方自行验收。
- 分支codex/q23-portfolio-reuse；无新Issue/PR，未推送。
- 产物提交b048a9de7bb375c892711ffb7c5d4dded1a98734；输入7002369e。
- 本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript；服务器/home/xihs/q1-campaigns/20260925-q23-portfolio-reuse。
- 冻结分支codex/q23-submit-freeze（ebce54dd）未变。正式阶段门禁NOT_RUN；未更新状态源、正式500配置或论文成绩。

## 已完成与产物

实验包装器程序/q23_portfolio_reuse.py接入原版Q2 protected与Q3 combined worker，原worker及正式入口与冻结提交无差异。仅切换GenerationReuse，软件评价准备缓存关闭。原始完整评分始终重算全球依赖与DDR竞争；最终再用原版完整重放及物理内存审计，不复用旧全局时长。

Q2选033/067/072，初解采用原Q1迁移；Q3选005/067/072，采用最新Q2种子及原Q3锚点。两臂12项，590秒、5核、种子0、96次提议，20%时间预留最终复核。完整组合按实际耗时自适应，序列可以分叉，不能套用普通joint的全程前缀相同要求。

证据目录图表/runs/20260925-A-q23-portfolio-reuse包含README.md、report.json、contract.json、jobs、rows、运行脚本/日志、原始文件哈希、服务器源码输入哈希及validation.json。程序/code_manifest.json、图表/全部结果.json、计算结果.md均记录本轮。

- 12项完整通过，无超时截断；最长483.705981秒，峰值子进程RSS922.71875MiB。
- 379共同方案完整官方结果哈希一致。242原始文件的下载与Git索引字节哈希核对通过；306服务器源码/输入与本机一致。
- 六组周期和搬运均持平。Q2样本均值4.899344693、总周期18,564,609、搬运350,297,504字节；Q3样本均值4.059202643、总周期17,737,921、搬运351,826,596字节。不是100图新成绩。
- 官方评分379→380。四组达到96次上限；Q2/072均14提议、25评分；Q3/072为35→36提议、32→33评分，但无最终改善。
- Q2/033总求解125.929→116.249秒，Q2/067为356.134→343.813秒；Q3/005为184.697→179.604秒，Q3/067为313.571→318.196秒。单次测量含服务器负载噪声，不宣称稳定提速。
- Q2/072的order_plan共43次均不命中、耗时88.42秒；context有49/55命中。昂贵调用的参数不同，整次结果无法复用。

## 接手复现

服务器Python3.12.14，原依赖环境/home/xihs/q1-runtime/run-python。真实启动：

```sh
nohup /home/xihs/q1-runtime/run-python -u run_portfolio_reuse.py > portfolio_reuse.log 2>&1 < /dev/null &
```

运行脚本已归档；每项真实命令见rows/*.json.command。复跑另设新目录，不覆盖原rows/jobs；保留合同及服务器来源哈希。暖初解的历史生成不在本轮计时中。

本机实际执行退出码0：

```sh
python -m unittest discover -s 程序/tests -p 'test_q23_portfolio*.py' -v
python -m py_compile 程序/q23_portfolio_reuse_report.py
python 程序/q23_portfolio_reuse_report.py 图表/runs/20260925-A-q23-portfolio-reuse
```

本机2项通过（2.818秒），其中固定动作测试包含7类候选及Q3缓存池，方案和随机状态一致；服务器完整组合1项通过（4.065秒）。完整JSON重放比较先规范化键类型，避免JSON落盘将整数键变字符串产生假差异，不放宽数值和字段。最小产物检查与git diff --cached --check通过。正式门禁NOT_RUN。

## 风险、接口和后续

- 决策：保持冻结提交，不因本轮结果自动推广或扩大100图。
- 可先拆解order_plan的不变准备，保持参数完整及隔离副本；再单独测试。小图要利用省下的时间，可另建两臂同时提高提议上限的对照，不能只给复用臂增加预算。
- 本轮80%搜索加20%最终复核与历史590秒纯搜索口径不同，不直接比较历史分数归因。
- 单种子六组不能代表全量，也未证明冷启动十分钟达标。源码不改模型物理规则，不更新正式入口或论文全量指标。
- q23_cache_search.py在此前实验分支已与冻结版不同；本轮沿用已冻结实验合同哈希。冻结分支本身以及原protected/combined、q2_current_submit.py、q3_submit.py保持不变，不能声称当前实验工作树1397项全部等同冻结分支。
- 无需用户解除的阻塞项。接收者自行填写验收结论，未代填ACCEPTED。
