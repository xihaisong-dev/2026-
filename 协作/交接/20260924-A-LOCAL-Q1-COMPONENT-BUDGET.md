# 交接：LOCAL-Q1-COMPONENT-BUDGET — 完整分量与结构预算控制

## 交付信息

- 本地编号：LOCAL-Q1-COMPONENT-BUDGET；无对应 Issue。
- 提交人 / 角色：A / 建模与计算。
- 接收人 / 角色：下一轮 A 操作者；B 仅引用实验讨论，正式五点仍沿用 v18。
- 时间（+08:00）：2026-09-24T00:20:45.525220+08:00。
- 交接状态：READY，未代填接收确认。
- 分支：codex/q1-component-budget；从 codex/q1-structure-seeds 的 0d7f846 继续。
- PR：Draft #11，https://github.com/xihaisong-dev/2026-/pull/11 。已推送，等待独立审阅；未合并。
- 产物提交 SHA：b2a3e8494026e3d16cb64689b202875cd788d108。
- 本机 worktree：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入与来源：继承 v18 的单核基准与 processed/q1 官方源码、100 图、固定配置；逐文件及输入原件哈希见本轮两批 summary.json 与 input_package.json。新增分量布局沿用上一轮已署名的用户参考工程，新增的是结构预算控制，不声称原始分量算法为原创。

## 已完成与产物

| 产物 | 内容 | 版本 |
|---|---|---|
| 程序/q1_structural_seeds.py、q1_experimental.py、q1_ablation.py | component_guard/slot；路由、单候选、观察隔离、槽位替换 | 本产物 SHA |
| 程序/q1_seed_campaign.py、q1_component_report.py | 可配置矩阵与可复核报告 | 本产物 SHA |
| 图表/runs/20260924-A-q1-component-primary | 14 图四核数三配置 168 次 | summary.json 与 source_snapshot |
| 图表/runs/20260924-A-q1-component-robust | 十图五核两种子三配置 60 次 | summary.json 与 source_snapshot |
| 图表/runs/20260924-A-q1-component-analysis | 配对表、路由、布局损失、与上轮比较 | summary.json / paired.csv / robustness.csv |
| 图表/runs/20260924-A-q1-component-execution | 服务器启动脚本、日志、来源与字节哈希核验 | 结果包 SHA256 6d5f2bbbfa97ee475d36a32f934f16c638e35212c9488ef80b36bb79e7d362a3 |
| 审查/问题一分量预算优化实验协议_20260924.md、问题一分量预算优化验证_20260924.md | 运行前规则及真实正负结果 | 本产物 SHA |

## 接手复现

环境：Python >= 3.10 标准库，按程序 README 原有 prepare 流程准备官方输入。服务器本轮使用 Python 3.12.14、20 逻辑核，主实验 12 worker 与稳健性 4 worker 并行；总墙钟 655.06 秒，所有本轮子进程已经退出。本机没有重复跑正式配置。工作目录为仓库根；下列输出目录必须不存在。

```powershell
python -m unittest discover -s 程序/tests -p 'test_q1*.py'
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/component-reproduce-primary --workers 12 --variants shared_region component_guard component_slot --cases case_017 case_045 case_048 case_065 case_077 case_002 case_028 case_063 case_067 case_085 case_006 case_040 case_090 case_097 --protocol 审查/问题一分量预算优化实验协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/component-reproduce-robust --workers 4 --variants shared_region component_guard component_slot --robustness --protocol 审查/问题一分量预算优化实验协议_20260924.md
python 程序/q1_component_report.py --primary 图表/runs/component-reproduce-primary --robustness 图表/runs/component-reproduce-robust --previous 图表/runs/20260923-A-q1-structural-seeds --prior 图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv --output 图表/runs/component-reproduce-analysis
```

实际命令和输出路径：server_execution.json 中保存服务器两个真实 argv；均退出 0。单元测试 80 项、退出 0、2.480 秒。报告对已交付目录执行退出 0；补充布局损失说明后在 `_tmp/component-budget/final-analysis` 再次生成并复制回交付分析目录。1314 个提交前证据文件的 Git index 与冻结工作文件逐字节一致，源码清单校验通过。实际工作源码检查通过；冻结快照保留原字节。

每次预算固定 12（1 固定单核复用 + 11 新评分），计 2508 次完整评分、228 次引用、228 次独立原版 A 最终核验。核验包括 Makespan、额外搬运、时间线、峰值和 Step3，全部通过。56 个基线重跑与原 v18 一致；101 个未评分分量候选的挑战者完整轨迹与计划等同基线。

主实验 slot：17 胜/39 平/0 负，总时间 165085175 → 164808910 cycles（下降 0.167347%）；额外搬运下降 0.991975%。guard：17/38/1，case_006 二核退步 0.335319%。双种子 slot 7/13/0，时间下降 0.280834%，搬运下降 1.120251%。028/063/067/085/097 五张重点图都保持基线结果。14 图 slot 五点为 1、1.851747、2.580496、3.200706、3.781434；不是 100 图五点。

## 风险、接口和下一步

- 明确取舍：相同十图上 slot 比上轮 seed_combined 总时间慢 0.221386%、搬运多 0.877729%；比上轮 seed_components 慢 0.012373%。这是相对原基线的稳健性改进，不能说比已有全部方案更快。正式默认不变。
- 只评估一个布局偏保守。case_077 的 2/3/4 核，上轮 LPT 更好，新静态排序只选 Pipe；case_017 还有后续 directed_split 路径变化。下界剪枝可靠不代表基于下界的排序可靠。
- 下一条具体操作：固定 slot 为稳定对照，单独验证“第一次分量候选确实改善后，才在同一 12 次预算内给第二种结构不同的布局机会”；保护已有后置拆分/重排，保持大图路由，不能写 case 编号特判。另将已通过规则冻结后做全 100 图验证。不要无条件恢复全部窗口和所有布局。
- 原始张量并集不是活跃缓存峰值；路由可能过于保守。当前条件没有声称容量违法或保证没有溢出。
- 替换普通随机机会前保留原提案构造和随机数消耗，但结构候选改善仍会改变父解及成本，不能保证所有图无退步。
- 14 图含历史项目用过的扩展图，不是独立盲测。保持未通过/负收益实验与计数，不做事后跨算法逐例取最小冒充线上方法。
- 数据接口仍为 node_to_subgraph/core_schedules；新增配置和路由统计只用于实验。q1_submit 默认未变。
- 求解秒数不包含固定单核冷计算及原版最终核验；当前样本都低于 600 秒，不是所有未来实例的硬保证。
- 正式阶段、人工审核、论文采用及最终交付门禁：本轮未推进，NOT_RUN；计算验证不代替人工接收。
- 受影响人：A 使用新实验配置，B 可引用带版本讨论，C 正式数值仍依据既有采用证据。无计算阻塞，接收者决定下一轮优先级。

## 接收确认（接收者填写）

接收人、检出 SHA、复现命令、时间及 ACCEPTED/CHANGES_REQUESTED：待接收者填写。
