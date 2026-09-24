# 交接：Q1-EVENT-20260924 — 事件排序验证、准备复用与100图全量

## 交付信息

- 任务 Issue / 本地编号：Q1-EVENT-20260924；无新增远程Issue。
- 提交人 / 角色：Codex / A端分析求解。
- 接收人 / 角色：后续A端；B/C操作者需经负责人确认采用后引用，不自动启动。
- 交付时间：2026-09-24T09:27:11.397282+08:00。
- 交接状态：READY。
- 分支 / PR：codex/q1-event-ranking-full100；本轮未创建PR。
- 产物提交 SHA：4d693a2efa5a1f4373a0f553789bf324115481aa。
- 本机worktree：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入提交 SHA：1aa466e4681597ff83d8422da08c0244b797a5b7。
- 输入文件及哈希：数据/processed/q1/manifest.json；全量冻结配置、100图输入及源码哈希见图表/runs/20260924-A-q1-event-ranking-v2-frozen/full_manifest.json。
- 阶段：研究分支实验交付；未更新正式默认、main、工作流阶段或人工门禁。

## 已完成与产物

|产物路径|内容|版本/证据|下游用途|
|---|---|---|---|
|图表/runs/20260924-A-q1-event-ranking-full100/|100图400配置、固定单核、逐例CSV、完整结果、冻结源码、审计|上述产物提交|全量比较及复现|
|图表/runs/20260924-A-q1-event-ranking-selection-audited/|24图事件排序同池对照、32组缓存等价、跨平台检查|V1验证129次|保留失败和选择依据|
|图表/runs/20260924-A-q1-event-ranking-v2-frozen/|统一回退策略、分片清单、V2等价、传输哈希、复现说明|400组均V2重新运行|冻结规则|
|图表/runs/20260924-A-q1-event-ranking-v2/|本机120组、服务器280组及真实命令日志|completed=true，零失败|原始记录|
|建模报告.md、计算结果.md、图表/全部结果.json|机制说明、完整成绩、限制和预算|本轮追加段落|写作与后续研究|
|程序/code_manifest.json|102份源码哈希和用途|已刷新|代码交付|

平均加速比1～5核：1、1.8349172085、2.5462379271、3.1610089648、3.6659026939。对上一版全量68胜330平2负；五核总时间下降3.667809%，额外搬运下降23.261093%。两核、五核平均指标略高于参考，三核、四核略低。五核搬运量仍高于参考，不能称各项全面胜出。

事件池重排序在开发与扩展的三核平均指标均退步，因此按预案选routes_gate_reuse：局部池内排序＋事件准入＋V2准备复用。没有逐case挑最好版本。缓存串行6组仅观测0.398125%的耗时下降，未证明显著提速。全量增益包含此前memory/hybrid结构路由的贡献。

## 接手复现

- 环境：本机Python3.14，服务器Python3.12.14，标准库；官方附件代码保持原字节。
- 工作目录：本worktree根目录。服务器运行目录为/home/xihs/q1-campaigns/event-ranking-20260924-v2。全部批次已结束，SSH已关闭。
- 求解实际命令：本机/服务器full_*_execution.json记录了完整argv；每组seed0、12机会，2～5核；本机2worker、服务器14worker。固定单核参考来源与结果哈希见summary。
- 从零复现可先按既有q1_io.prepare导入原附件；为q1_opportunity_campaign提供100图固定参考目录（case/single/row.json与evaluation.json.gz）及对应summary。当前用的是_tmp/event-ranking/references，来源为上一版全量single目录。可不传verified-plan-runs，重新做所有原版复核，但大图复核耗时明显增加。
- 必须使用source_snapshot中的源码恢复程序目录，才能得到完全相同的运行源码哈希。当前工作树仅报告脚本有功能扩展；q1_ablation和campaign做了EOF/换行规范化，算法逻辑相同；冻结字节未改。

实际分析命令（输出目录已存在时换新目录）：

```powershell
python 程序/q1_event_full_report.py --run 图表/runs/20260924-A-q1-event-ranking --output 图表/runs/20260924-A-q1-event-ranking-selection-audited
python 程序/q1_event_v2_freeze.py --selection 图表/runs/20260924-A-q1-event-ranking-selection-audited --output 图表/runs/20260924-A-q1-event-ranking-v2-frozen
python 程序/q1_event_full_report.py --run 图表/runs/20260924-A-q1-event-ranking-v2 --selection 图表/runs/20260924-A-q1-event-ranking-v2-frozen --output 图表/runs/20260924-A-q1-event-ranking-full100
python -m unittest discover -s _tmp/event-ranking/frozen-v2/程序/tests -p 'test_q1*.py'
```

实际检查：上述分析命令退出0；两端100项单测通过；400配置输入/冻结代码/输出哈希、预算与四基础粒度、原版验证谱系、统计口径通过。已检查7147份程序/结果文件的Git暂存blob与本机字节一致；冻结快照只豁免原有EOF空行的格式警告，不改快照。原始日志、audit.json、source_and_size_audit.json给出证据。正式阶段门禁和人工批准：NOT_RUN / 未申请变更。

## 风险、接口和后续

- 仅seed0；无可靠最优下界。参考工程预算不同，不由成绩差宣称同求解时间效率。
- 006三核31819→32925、四核31094→31129，两组退步原样保留。
- 最长搜索363.859秒，无搜索超600秒；不包含单核冷生成及独立复核。服务器全量墙钟1489.317秒，本机104.246秒，不能把并行完成时间当单个算法加速比。
- 正式搜索4400次，额外诊断1705次，合计6105次完整搜索评分；正式原版最终复核16次、诊断59次，严格原版验证复用480次。单测另计。
- 新增实验开关event_seed_rank、preparation_reuse及配置routes_event_rank/routes_event_reuse/routes_gate_reuse。正式入口默认不变。
- 五核对参考平均分差的主要损失图为069、071、050、068；后续先检查这些小/中图的预算机会与主导分量结构，保留本全量基准，勿盲目扩大搜索空间。
- 影响接收人：A端后续优化；若写作选本版，B更新表图和结论、C复核，须绑定本产物SHA，不把未采用的事件排序写成有效机制。
- 下一条操作：检出产物SHA，运行只读分析到新目录，核对五个平均点及400组唯一性，再决定是否采纳为正式版本。无计算任务遗留，无需继续服务器进程。

## 接收确认（接收人填写）

- 接收人/验收时间：待接收人填写。
- 实际检出的产物SHA：待填写。
- 验证命令与结果：待填写。
- 结论：待填写，提交方不代填ACCEPTED。
