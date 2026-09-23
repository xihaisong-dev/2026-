# 交接：LOCAL-Q1-COMPONENT-FOLLOWUP — 条件第二布局

## 交付信息

- 本地编号 LOCAL-Q1-COMPONENT-FOLLOWUP，无对应 Issue。
- A 建模与计算交给下一轮 A；B/C 仅引用原型讨论，正式全量数值不变。
- 日期 2026-09-24（北京时间），状态 READY；未代填接收确认。
- 分支 codex/q1-component-followup，父版本 f3c8f6d（上一轮 PR #11 所在分支），本轮无新 PR，未合并 main。
- 产物提交 d27eea86b853b4f08654ed8b0d669c8b9438c5bb。
- worktree：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入继承经审计 processed/q1 和 v18 固定单核；源码、输入、配置、协议哈希见两批 summary.json。场景 A 官方接口及正式默认不变。

## 交付与结果

新增 component_followup：首次分量候选严格降低 Makespan 才解锁另一种节点分组；最多两次结构评分，总预算仍12。第二候选仅替换普通随机提案或已评价的等价提案；保持核心身份和顺序判重，四档粒度仍构造。无机会时跳过。

- 程序：q1_structural_seeds.py / q1_experimental.py / q1_ablation.py；报告 q1_followup_report.py；测试 test_q1_component_budget.py。
- 协议与验证：审查/问题一条件第二布局实验协议_20260924.md、问题一条件第二布局验证_20260924.md。
- 证据：图表/runs/20260924-A-q1-followup-{primary,robust,analysis,execution}。
- 14 图四核数 seed=0，112 次；十图五核 seeds=1/2，40 次。152 份最终原版 A 复核全部通过。合计1672正式完整评分、152固定单核引用、152最终核验；单元测试另计。
- 主实验相对 slot：2胜54平0负，164808910 →164784036 cycles（下降0.015093%）；额外搬运增加229440 bytes（0.008017%）。case_077两核下降0.798054%，case_040两核下降15.906230%，后者包括后续搜索收益。重点五大图20组持平。
- 14图平均加速比1～5核：1、1.876696、2.580496、3.200706、3.781434。只有二核点变化，不是100图成绩。
- 稳健性20配对全持平；第二布局未实际评分，不能称为跨种子有效性确认。
- 主实验解锁17次，实际第二评分4次：两次当场改善、一次持平、一次较差，较差候选不替换最优。全部来自等价local_reschedule机会。12组缺少可替换机会。
- 76个slot重跑与上一轮轨迹和最终方案一致；72个没有第二评分的挑战者与slot轨迹和方案一致。
- 83项测试通过：服务器Python3.12.14为3.248秒，本机Python3.14规范化后为2.634秒，均退出0。

## 复现与执行

仓库根目录，Python>=3.10标准库；按程序README准备原始附件，保留固定单核参考。输出必须新目录：

```powershell
python -m unittest discover -s 程序/tests -p 'test_q1*.py'
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/followup-reproduce-primary --workers 12 --variants component_slot component_followup --cases case_017 case_045 case_048 case_065 case_077 case_002 case_028 case_063 case_067 case_085 case_006 case_040 case_090 case_097 --protocol 审查/问题一条件第二布局实验协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/followup-reproduce-robust --workers 4 --variants component_slot component_followup --robustness --protocol 审查/问题一条件第二布局实验协议_20260924.md
python 程序/q1_followup_report.py --primary 图表/runs/followup-reproduce-primary --robustness 图表/runs/followup-reproduce-robust --prior-primary 图表/runs/20260924-A-q1-component-primary --prior-robustness 图表/runs/20260924-A-q1-component-robust --previous 图表/runs/20260923-A-q1-structural-seeds --output 图表/runs/followup-reproduce-analysis
```

真实服务器argv和退出码见execution/server_execution.json。服务器20逻辑核、主实验12worker与稳健性4worker并行，总墙钟415.434秒。全部已退出，无未完成计算。输入及引用单核只读复用上一批独立目录；本机未重复计算正式配置。

代码清单校验通过；940个证据文件在Git暂存区与实际冻结文件逐字节一致。求解源码从服务器运行字节到仓库提交字节仅CRLF转LF，逐文件映射见execution/source_identity.json，规范化后再次通过83项测试。运行时原始协议副本在execution/protocol.md，SHA与summary一致。最终源码快照与产物原字节均保留。

输入包SHA256 f85be71adc0f9b3e6fa05382b8fd5f2fc33c0dff905b59a0cc928fc81b175f1b；结果包SHA256 cd5e44377f79086804240f7fe245a6a01ac06bef8e01c65203ada143f1558e09。服务器目录 /home/xihs/q1-campaigns/component-followup-20260924-r01；本地临时包 _tmp/component-followup，不随Git提交。

## 限制与下一步

不能称为全面改善：共同十图仍比seed_components总时间慢0.011023%、比seed_combined慢0.220033%，本轮总搬运略升，三至五核点未变。结构路由和第一候选静态排名仍可能漏掉高质量初解。成本观察和父解变化可能影响后续搜索，因此机会保护不等于绝不退步。

满足预定开发组总时间改善和大图不退步条件，只意味着可进入全量验证，不代表正式采用。下一步宜先分析12组无可替换机会的预算台账，再决定更广的去重还是重新分配机会；不得无条件挤掉真实拆分/重排，也不得直接全量替换默认。若做全量比较必须固定同一版本，使用赛题逐例平均定义，不能把14图平均与参考100图平均相比。

正式阶段门禁、论文采用和人工接收：NOT_RUN。没有修改Q2或根目录其他任务，无外部消息发送。接收者自行填写ACCEPTED/CHANGES_REQUESTED。
