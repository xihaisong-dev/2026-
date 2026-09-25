# 交接：Q1-TIMED-PORTFOLIO — 十分钟限时组合开发证据

## 交付信息

- 本地编号：Q1-TIMED-PORTFOLIO；相关 Issue：不适用，本轮为用户直接授权的优化。
- 提交人/角色：A；接收人：下一轮 A 求解操作者。当前不得作为 B 的全量正式新成绩派稿。
- 交付日期：2026-09-25（+08:00）；交接状态：READY（开发证据，不代表正式验收通过）。
- 分支：codex/q1-timed-portfolio；产物提交：79950887；输入提交：1ee83007。
- Worktree：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 输入：数据/processed/q1，调用 q1_io.verify 校验原附件；各 contract.json 记录图及源码摘要，最终源码清单见报告目录 source_manifest.json。
- 阶段：延续既有问题一开发验证；未变更工作流阶段。全100图冻结版本正式门禁 NOT_RUN。

## 已完成与产物

|路径|内容|用途|
|---|---|---|
|程序/q1_timed_portfolio.py|硬截止、合法保底、逐次原版官方检查点、组合搜索|单配置实验入口|
|程序/q1_timed_candidates.py|前沿切分、向量装箱、局部边界、变体列表调度|启发式组合|
|程序/q1_timed_campaign.py|多进程实验编排与旧结果对比|开发验证|
|程序/q1_timed_verify.py|独立官方重放全部字段一致性|复核|
|图表/runs/20260925-A-q1-timed-report-v2/|README、evidence、源码摘要、测试日志|唯一新报告入口|
|计算结果.md|本轮开发结果摘要|口径说明|

## 接手复现

使用现有仓库 Python 环境；先按 README 导入官方附件。从仓库根目录执行，输出目录必须不存在：

```powershell
python 程序/q1_timed_portfolio.py 数据/processed/q1/data/case_071.json -n 5 --seconds 590 --seed 0 --output 图表/runs/q1-timed-reproduction
python 程序/q1_timed_verify.py --runs 图表/runs/q1-timed-reproduction --output 图表/runs/q1-timed-reproduction-replay.json
python -m unittest discover -s 程序/tests -p test_q1_timed_candidates.py -v
python -m unittest discover -s 程序/tests -p test_q1_experimental.py -v
```

实际测试：上述两套单测共12项通过；六份 cold/extension/large 独立重放和三份 large-final/holdout 独立重放，全字段一致。证据分别在 timed-cold/independent_replay.json、timed-holdout/independent_replay.json。实际最终源码冒烟命令为：

```powershell
python 程序/q1_timed_campaign.py --cases 71 --cores 5 --seconds 20 --workers 1 --cold --output 图表/runs/20260925-A-q1-timed-final-smoke
```

退出码0；18757→12257 cycles，墙钟16.094秒。不同硬件的截止点不同，不保证重新搜索输出完全相同；保存方案的官方重放应一致。五图20配置是 earlier cold 批次，不能冒充最终源码的完整冻结对照。每次源摘要在对应 contract，早期部分版本仅保存源码摘要与方案；可复核方案，不承诺重建每个旧版本的搜索轨迹。

## 风险、接口和后续

- 原 q1_submit 默认策略未替换，旧100图/500组正式结果未改写。
- 新增 initial_plan/on_incumbent 可选参数；旧调用默认行为不变。提供多核 initial_plan 时 singlecore_makespan/speedup 为 null，禁止当单核计分基准。
- 五图20配置19胜1平；补测8配置4胜4平。新预算多于旧12候选，不是同预算算法归因。
- 大图067五核改善1.2095%；072五核590秒试验退步0.02197%。072单份方案原版官方重放约300秒，是这一轮明显的求解开销瓶颈。限时单位为单case×核数，不包含重新生成固定单核计分基准或额外审计。
- 失败、超时和退步全部保留，不以逐版本/逐配置事后最好生成正式新成绩。
- 下一步：针对大图建立可中断的分阶段预算，研究官方等价加速评估/核内准备复用，留足原版最终复核时间；再冻结规则做100图2～5核对照。不得直接把候选预测或历史事后择优作为成绩。
- 跨目录影响：程序/、本轮图表/runs/、计算结果.md、此交接；B/C 暂无需改论文。
- 决策：保留独立实验入口，不推广替换默认；没有人工批准或门禁通过声明。

## 接收确认

由接收人填写；提交方未代填。
