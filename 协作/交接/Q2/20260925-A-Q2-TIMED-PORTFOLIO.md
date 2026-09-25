# 交接：Q2-TIMED-PORTFOLIO — 五核限时算法组合研发

## 交付信息

- 用户任务：基于问题一思路，用不同算法组合优化问题二，主要五核，单配置10分钟内；不限定现有算法。
- 提交人：A端；接收人：后续A计算操作者，B/C仅可引用已标清范围的研发结果，不替换正式章节成绩。
- 日期：2026-09-25（+08:00）；状态：READY（研发交接，非正式全量交付）。
- 分支：codex/q2-timed-portfolio；PR不适用，未推送GitHub。
- 产物SHA：d6a87abe8e2f4fd2ac11191857e90b74307e5e20；首轮冻结源码2d1dbd67。
- 输入提交：f312a52fc74c0835fe393b4ace2ec0c6fb5081f3。
- 本地工作目录：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 正式门禁NOT_RUN，状态文件未改；当前正式问题二100图五核均值仍为4.159974。

## 已完成与产物

|路径|内容|
|---|---|
|程序/q2_timed_portfolio.py|限时原版官方评价、原子回退、基础预算保护、结构自适应有界组合|
|程序/q2_timed_pilot.py|冻结输入/配置/源码/种子，三臂及指定臂配对，独立完整结果官方重放|
|程序/report_q2_timed.py|生成报告，不修改正式成绩|
|图表/runs/20260925-A-q2-timed-report/|README、数值证据、11项测试记录及37份最终结果独立重放记录|
|图表/runs/20260925-A-q2-timed-paired-v2/|7图×3臂，60秒同上限、最多96次提议|
|图表/runs/20260925-A-q2-protected-pilot/|相同七图protected规则|
|图表/runs/20260925-A-q2-protected-confirmation/|冻结规则后009、039，旧扩展与protected对照|
|图表/runs/20260925-A-q2-seeds/|039种子1、2，60秒|
|图表/runs/20260925-A-q2-cold071/|无迁移种子冷启动20.297秒，10038周期|
|图表/runs/20260925-A-q2-timed-large/|服务器067、072第一版portfolio，590秒上限及官方重放|
|output/q2-timed-20260925.zip|服务器冻结包，SHA256 f4f7cfcc6e1707e7f7e6dec292dbb2e9f3e13ed26414681d3739288ad6386ecf|

## 思路与实际结论

场景B同核子图组成一个核内Task，同核切换不清空缓存。复用问题一的划分/装箱构造时只借鉴结构，不借用A的Task时长或同步成本。所有接受决策来自未改动的官方B评估器，容量、共享DDR、跨核释放与四Pipe依赖均重新计算。

保留已有初解菜单及普通J机会；新组合包括通信权重重映射、相对拓扑粒度、生命周期顺序、迁移/拆分/边界联合调整、合法插入。protected先给旧局部搜索最多32次提议/剩余时间40%的机会，再混合完整分量向量装箱及通信前沿划分。结构先验与实际改善/耗时决定剩余份额，保留探索概率；没有case编号白名单，也没有穷举所有划分。

九图（017、032、048、055、064、071、088、009、039）统一protected：四胜五平零负，算术平均加速比3.163598→3.233938；总周期699746→672786（下降3.852827%）；额外搬运19727888→16624208（下降15.732449%）。同上限旧扩展为3.221469、681299周期。不能把这些小样本均值与正式100图4.159974直接比较。

039最明确：338925→313002周期；旧扩展321514。日志归因先有joint改善至323321，再有packing至313515、313002。种子0/1/2为313002/308867/323354，均优于原方案但幅度波动。七图子集中protected平均加速比3.112495略低于旧扩展3.113806；因此不能声称组合普遍胜出。

大图使用第一版portfolio而非protected：067为13383635周期、444.267秒；072为4812649周期、535.350秒。相对原版本周期都下降，072搬运却大幅增加。不得用每图挑不同试验臂的最佳值，拼出一个正式成绩。

## 接手复现

Python3.12.14，标准库；固定原输入与官方代码由q2_evaluator.load验证。新输出目录不能已存在。

```text
python 程序/q2_timed_pilot.py --seconds 60 --output 新目录/paired
python 程序/q2_timed_pilot.py --arms protected --seconds 60 --output 新目录/protected
python 程序/q2_timed_pilot.py --cases 9 39 --arms ordinary_extended protected --seconds 60 --output 新目录/confirmation
python 程序/q2_timed_portfolio.py 数据/processed/q1/data/case_039.json --cores 5 --arm protected --seconds 590 --migration 图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_039_multicore_res.json --output 新目录/039
python 程序/q2_timed_portfolio.py 数据/processed/q1/data/case_071.json --cores 5 --arm protected --seconds 60 --output 新目录/cold071
python -m unittest discover -s 程序/tests -p test_q2.py -v
python -m unittest discover -s 程序/tests -p test_q2_timed_portfolio.py -v
python 程序/report_q2_timed.py
```

实际两组测试均退出0，8+3项通过。37份最终方案独立官方重放，JSON键归一后全字段相同。首次回放断言曾受JSON整数键转字符串影响，已修复并保留失败目录，未将失败运行计入指标。产出最小检查及git diff --check通过，不代表正式阶段门禁通过。

## 计时、部署与限制

- 每次完整官方评价计入求解；已有官方有效结果立即持久化，再原子更新verified.json，硬中断只回退已验证方案。首次评价尚未完成时明确no_verified_solution。
- 590秒截止预留进程清理余量；本轮大图小于10分钟，但不证明全部100图冷启动满足目标。
- 暖启动使用同一Q1种子，生成成本不计入；固定单核分母、实验用独立复核不计入求解。入口不用历史周期查表作决策。无migration走冷启动分量初解。
- wall-clock自适应包含实测耗时，相同seed也可能因负载改变轨迹。当前只对039检查三个种子，未证明全量稳健性。
- 服务器独立目录/home/xihs/q1-campaigns/20260925-q2-timed；本轮两个Q2任务已完成，无需恢复。未改动另一个Q1全100批次。
- 下轮先决定是否接受072的搬运代价，再冻结protected规则做全100五核同上限对照；应另核查冷启动与未完成首评的失败率。不要直接替换q2_current_submit或正式500份输出。
- 接收确认留空，由接收人填写；未启动B/C，也未代填人工验收。
