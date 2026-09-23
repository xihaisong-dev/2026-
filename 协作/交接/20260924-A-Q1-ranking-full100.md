# 交接：20260924-A-Q1 — 固定池排序与100图验证

## 交付信息

- 本地编号：20260924-A-Q1-ranking-full100；无新增Issue。
- 提交人：A；接收人：用户及后续A/B操作者。
- 交付时间：2026-09-24（+08:00）；状态：READY，未代填人工接收。
- 分支：codex/q1-ranking-full100；未推送、未修改main。
- 产物提交SHA：23cfb90f3b2830664c77d644c77e279e9472b51f
- 工作目录：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入提交：fe48947；正式阶段及人工门禁没有推进。
- 输入哈希：继承数据/processed的导入清单，报告程序已核验；服务器包哈希和冻结源码见ranking-execution。

## 已完成与产物

| 路径 | 内容 | 用途 |
|---|---|---|
| 图表/runs/20260924-A-q1-ranking-audit | 12条搜索重建、18个固定候选池共50候选 | 预算及排序证据 |
| 图表/runs/20260924-A-q1-ranking-validation | 14图×4核×2方案，112份 | 同预算主验证 |
| 图表/runs/20260924-A-q1-ranking-robust | 10图×5核×2种子×2方案，40份 | 稳健性 |
| 图表/runs/20260924-A-q1-ranking-full100 | 冻结方案100图×4核，400份 | 全量原版复核结果 |
| 图表/runs/20260924-A-q1-ranking-analysis | 报告、逐例CSV、损失结构、加速比图 | 写作及下一轮诊断 |
| 图表/runs/20260924-A-q1-ranking-execution | 实际命令、服务器日志、冻结选择、包哈希 | 复现和预算追溯 |

## 接手复现

- Python标准库求解；服务器Python3.12.14，20逻辑核、正式全量16worker。绘图可选matplotlib3.11.2。
- 完整运行命令：执行记录full_execution.json中三项command保存了实际参数（含100图完整列表）；本地复现命令见程序/README.md“冻结局部排序全量实验”。更换所有输出为新目录，禁止覆盖本轮证据。
- 固定配置：component_local_rank，核数2/3/4/5、seed0、12机会；其中1次既有官方整图单核引用、11次完整评分。单核曲线点为1。
- 服务器85测试通过，日志full_tests.log；本机同85测试已通过。400份最终原版复核通过，失败0；56份重复小矩阵结果及方案完全相同。
- 实际分析命令（已成功执行，退出0；重跑应改output）：

```powershell
python 程序/q1_ranking_full_report.py --audit 图表/runs/20260924-A-q1-ranking-audit --validation 图表/runs/20260924-A-q1-ranking-validation --robustness 图表/runs/20260924-A-q1-ranking-robust --prior-validation 图表/runs/20260924-A-q1-followup-primary --prior-robustness 图表/runs/20260924-A-q1-followup-robust --full 图表/runs/20260924-A-q1-ranking-full100 --execution 图表/runs/20260924-A-q1-ranking-execution --baseline 图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv --output 图表/runs/20260924-A-q1-ranking-analysis
python 程序/q1_ranking_plot.py --analysis 图表/runs/20260924-A-q1-ranking-analysis --font C:/Windows/Fonts/simhei.ttf
python 工具/rendered_visual_audit.py --workspace . --strict
```

- 全量1～5核平均点：1、1.814348916、2.481664517、3.071797338、3.545442821。均为逐例T1/Tk算术平均。
- 全量原基线对照197胜203平0负；排序单因素56对10胜46平0负、时间下降0.023081%；不能将累计全量改善归因于排序。
- 预算：本轮诊断182次完整评分+12次单核引用；同预算验证1672次评分+152次引用+152次最终复核；全量4400次评分+400次引用+400次最终复核。局部准备单独计时，未隐藏完整全局仿真。测试调用另计。
- 冻结源码字节与工作区相符，3589份证据文件的Git暂存字节与落盘字节核对一致。CSV/历史JSON保留原CRLF以保持来源哈希；diff检查使用cr-at-eol通过。
- 图形已目视检查无裁切；工具检查0critical/0warning。未做论文集成验收；不能当作最终论文PDF合规证明。

## 风险、接口和后续

- 正式默认、main和已采用全量结果均未替换。当前为可追溯实验分支。
- 排序原始分数的Spearman并列采用平均秩；audit冻结旧汇总含生成顺序破平局，最终报告保留两种统计，选择遗憾及前两名覆盖率不受影响。
- 参考工程搜索预算不同；总时间更低并不代表赛题平均加速比更高，本方案五核3.545443仍低于参考3.651513。
- 4组搜索超过600秒，最长864.298秒，未计固定单核冷计算及最终复核，也受到16并发影响。
- 下一轮：先核查case_058/039/072的union-footprint筛选是否假阳性；再对case_009/100/040主导分量做有界切分、小分量保持完整。单独冻结协议与预算，保留028/067大图保护组，不回改本轮报告。
- 15次核心置换评分仅证明这批结果相同，尚未证明所有方案对编号和事件并列顺序不敏感，勿直接做跨方案缓存。
- 影响：新增可选配置、报告脚本及证据，不改变官方输入输出接口；写作应引用本分支证据并明确实验状态。
- 阻塞依赖：无；服务器任务已全部结束，SSH已关闭。

## 接收确认（接收人填写并提交）

未填写，待接收人核验产物SHA与证据。
