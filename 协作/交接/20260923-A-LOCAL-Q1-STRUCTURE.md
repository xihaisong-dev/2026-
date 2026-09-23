# 交接：LOCAL-Q1-STRUCTURE — 结构初解同预算对照

## 交付信息

- 任务 Issue / 本地编号：LOCAL-Q1-STRUCTURE；本地实验，无关联 Issue。
- 提交人 / 角色：A / 建模、程序与实验。
- 接收人 / 角色：后续 A 操作者；B 可引用研究讨论，不能替换正式 100 图成绩。
- 交付时间（+08:00）：2026-09-23T23:48:20.802187+08:00
- 交接状态：READY。
- 分支 / PR：codex/q1-structure-seeds；本次未创建 PR。
- 产物提交 SHA：18c021321a03eca139004d12104aa7c733713892。
- 本机 worktree：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入提交 SHA：2e4febdea97d376d556a1e9655abf9baa45f5d1e。
- 输入来源：用户工程 SHA256 48aaca6e46f9ddc2d0e846e303dfe841bec2f8f0ab12afeb0898b7b7805d9e8f；赛题数据、配置、官方源码与单核基准哈希见两批 summary.json。全部输入从既有审计后的 processed/q1 使用。

## 已完成与产物

| 产物路径 | 内容 | 版本 / run-id | 下游用途 |
|---|---|---|---|
| 程序/q1_structural_seeds.py、q1_experimental.py、q1_ablation.py | 三族有界结构候选、规范化去重与预算保护 | 产物提交 | 独立实验开关 |
| 程序/q1_seed_campaign.py、q1_seed_report.py | 主实验、稳健性及报告生成 | 产物提交 | 复现 |
| 图表/runs/20260923-A-q1-structural-seeds | 200 次主实验、冻结源码、每组计划/评价/搜索/复核 | summary SHA256 269787682edd99b39de8dabf859a5301de4d50dbe1e56abfdae489528c5ee3a8 | 同预算对照 |
| 图表/runs/20260923-A-q1-structural-robust | 40 次双种子五核实验 | summary SHA256 ecb475700ba647430e2155539e5ff654bdf5780d4c000c41fac49d38465e2735 | 稳健性 |
| 图表/runs/20260923-A-q1-structural-analysis | 240 组配对表及汇总 | summary.json、paired.csv、robustness.csv | 统计/写作 |
| 图表/runs/20260923-A-q1-structural-execution | 分片清单、跨平台复核、服务器结果、源文件谱系 | 合并包 SHA256 bbf6e0416ede924a4376a68dbebc0c2b5194067857c674c1a68d923ffd3b53eb | 运行审计 |
| 审查/问题一结构初解同预算实验协议_20260923.md、问题一结构初解同预算验证_20260923.md | 预定协议与完整正负结果 | 产物提交 | 审阅 |

## 接手复现

环境：Python >= 3.10 标准库；使用原有 prepare 流程准备 `数据/processed/q1`。固定单核引用来自 `20260923-A-q1-v18-merged`，不得重优化分母。服务器运行 Python 3.12.14。工作目录为仓库根，输出必须使用全新目录。

```powershell
python -m unittest discover -s 程序/tests -p 'test_q1*.py'
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/q1-seed-reproduce-primary --workers 12
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/q1-seed-reproduce-robust --workers 4 --robustness
python 程序/q1_seed_report.py --primary 图表/runs/q1-seed-reproduce-primary --robustness 图表/runs/q1-seed-reproduce-robust --prior 图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv --output 图表/runs/q1-seed-reproduce-analysis
```

实际执行上述测试退出 0，75 项通过；实际批次输出为已交付的 structural-seeds/robust。原汇总命令对应两目录，退出 0；后续为补充搬运分解和中断计时说明，另在 `_tmp/structural-server/final-report-analysis` 重新生成同数据汇总并核验、复制回交付目录。源码快照按字节保留；工作源码仅规范换行/末尾空行，算法 AST 一致，报告脚本补充统计的变更见 source_provenance.json。

主实验：十图 017/045/048/065/077/002/028/063/067/085，2～5 核、seed=0、五方案。稳健性：同十图、五核、seed=1/2、基线和组合。每次 12 个唯一评价机会，含固定单核复用 1 次；最终官方 A 重放另计，不参与选优。验收标准：预算和前三个初解一致、四种基础粒度均尝试、最终五类官方字段完全一致。240 组全部通过；基线与既有 v18 40/40 一致。

主实验组合 26 胜/8 平/6 负，Makespan 合计下降 0.383374%，额外搬运下降 1.876083%；完整分量 16/23/1，分别下降 0.175188%、1.030899%。组合旧五图时间下降 21.0936%，反例组仅 0.0760%。双种子组合 10/3/7。十图组合平均加速比五点 1、1.878236、2.746881、3.494968、4.145261；严格逐例比值平均。

阶段与门禁：原型增强，未调用阶段推进；正式阶段、人审、论文采用与最终交付门禁未改变（本轮 NOT_RUN）。源及指标哈希、240 次原版重放、75 单元测试属于计算证据，不代替这些门禁。

## 风险、接口和后续

- 正式 adopted=shared_region 不变。十图不是盲测或全部 100 图，不得更新正式五点为本轮数值。
- case_028 四核无效分量初解挤掉后置重排；case_002 五核三个窗口挤掉后置有效拆分；case_085 观察成本和搜索路径改变后略退步。不能新增 case 编号特判。
- 优先以完整分量作为较小挑战者。单独验证减少窗口评价、收紧结构门槛及保护后置拆分/重排；规则冻结后再做全量同预算对照。组合不是无退化替代方案。
- 原始调度输出接口仍为 node_to_subgraph 与 core_schedules。新 row 元数据：部分已完成搜索因中断丢失外层计时，solve_seconds=null、solve_timing_complete=false；search_internal_seconds 仅内部秒数，不能冒充完整耗时。
- 本地完成 228 后独占分派服务器 12；4 组只补复核，8 组新搜索。服务器 12 worker 批次 146.50 秒，不含上传和两个跨平台复核。所有服务端本轮子进程已退出。冻结源、输入及两样本完整跨平台结果一致。
- 完整运行计 2640 评分、240 固定单核复用、240 最终核验；另 2 跨平台核验。中断在途耗费未知，未混入以上合计；不能把该合计声称为包括失败尝试的全部花费。
- 混合主机和并发计时不可作严格运行加速归因。四组没有完整秒数；当前实验不是未来全部图 600 秒硬保证。
- 生成算法归属用户提供工程，非本方独创；没有移植其 A/B 证书引擎。
- Git 保留证据的 CRLF 和 EOF 原字节以匹配哈希，普通 diff --check 会对冻结副本给出格式提示；实际工作源码为 LF。不要为消除冻结副本格式提示而修改证据。
- 接口受影响人：A 读取新实验配置；B 仅引用带版本的实验讨论；C 正式章节数值仍按已采用基线。阻塞：无计算阻塞，等待下轮方案选择，不代填接收结论。

## 接收确认（接收人填写并提交）

- 接收人 / 验收时间：待接收人填写。
- 实际检出 SHA / 验证命令 / 结论：待接收人填写。
