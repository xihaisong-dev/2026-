# 交接：A-q1-opportunity-budget — 新候选机会成本筛选失败复盘

## 交付信息

- 本地编号：A-q1-opportunity-budget；Issue/PR：不适用，本地实验分支。
- 提交人 / 角色：Codex / A，分析、编程与求解。
- 接收人：用户及后续A操作者；本轮不派B改正式成绩。
- 交付日期：2026-09-24（+08:00）。状态：READY，未代填人工验收。
- 分支：codex/q1-opportunity-budget，未推送。
- 产物提交 SHA：28f90d8532a6dc3b32e6cd987e6dbc04accd318a。
- 本机目录：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 输入提交：6e48ee0；默认、main、正式阶段及人工门禁均未更改。
- 原始官方附件SHA256：3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9。
- 本轮冻结输入包SHA256：f4976e9d8a85c4dfeeeffcbec2bdde1739506fc37a3e23aa933ef6c06b3d1774。

## 已完成与产物

| 路径 | 内容 | 版本 | 下游用途 |
|---|---|---|---|
| 图表/runs/20260924-A-q1-opportunity-budget | 32组search/plan/result、冻结代码、运行日志与复核谱系 | evidence.zip SHA256 47acf9acb0c40005591e42060ba89e72a8713b5451771de79d0605c3c7e7e909 | 原始证据 |
| 图表/runs/20260924-A-q1-opportunity-analysis-v2 | 报告、同池误筛诊断、预算核对 | 本提交 | 应采用的分析版本 |
| 审查/问题一候选机会成本验证协议_20260924.md及json | 8图开发、预选16图扩展和停止条件 | 开跑前冻结 | 禁止事后放宽 |
| 程序/q1_opportunity.py等 | 同口径局部成本筛选、自动结构路由、严格最终复核复用 | 本提交 | 仅实验开关，不采用筛选 |

## 接手复现

- Python标准库；服务器Python3.12.14，本机Python3.14。依赖题目已审计processed数据、固定单核references及历史原版验证结果。
- 服务器工作目录：/home/xihs/q1-campaigns/opportunity-budget-20260924-r02。
- 实际批次命令（复跑请另建输出目录；历史目录勿覆盖）：

```bash
/home/xihs/q1-runtime/python-3.12.14/bin/python3.12 -u 程序/q1_opportunity_campaign.py --reference-run references --output runs/development --workers 16 --variants routes_guarded --cases case_058 case_039 case_072 case_009 case_100 case_040 case_028 case_067 --protocol 审查/问题一候选机会成本验证协议_20260924.md --verified-plan-runs /home/xihs/q1-campaigns/ranking-full100-20260924-r01/validation/图表/runs/20260924-A-q1-ranking-full100 /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_memory /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_hybrid
```

- 批次退出0，完成32组；扩展条件False，16图128次运行没有启动。seed0、2～5核、12次机会、四基础粒度；服务器16worker。
- 实际本机分析命令退出0：

```powershell
& 'C:/Users/Lenovo/AppData/Local/Programs/Python/Python314/python.exe' 程序/q1_opportunity_report.py --run 图表/runs/20260924-A-q1-opportunity-budget --output 图表/runs/20260924-A-q1-opportunity-analysis-v2
```

- 重做分析应将output改为未存在目录。旧analysis目录保留为尚未增加开发组误筛诊断的中间报告，以v2为准。
- 93测试通过（tests.log）；32组输入、冻结代码、方案、完整结果与预算验证通过；383个新证据文件暂存字节逐个与磁盘一致，diff --check通过。
- 搜索352次完整评分+32次固定单核引用。32次最终验证复用已原版复核的字节相同方案，且完整评价输出严格一致；不复用搜索评分，不增加搜索机会。CLI冒烟另计，不混正式矩阵。
- 正式mm阶段门禁：NOT_RUN，本轮实验不改变状态文件或人工批准。

## 风险、接口和后续

- 筛选未采用：对上轮未筛选路由0胜30平2负，时间+0.617833%、额外搬运+3.604802%。不能用对更旧基线的20胜11平1负掩盖退步。
- 6个拒绝中误拒2个（039四核、072两核）；放行24个中4个无收益。028四核坏候选仍挤掉有效搜索，最终比旧基线慢17880cycles。
- 同池、同当前解已核验，独立核内局部回放不能可靠筛选全局收益。不要按这几图事后调整阈值或逐例择优。
- 新字段opportunity_comparison记录局部预测与筛选；verification_reused及verification_reuse.json记录最终验证复用来源。
- 16并行下本批最大搜索237.490秒；不含单核冷基准和原版复核，不据此宣称所有大图端到端达标。
- 第一次启动因参数遗漏在计算前失败，failed_startup保留；修复后独立r02冻结重跑。
- 下一条操作：固定候选池诊断共享DDR并发下的预测残差，并审计被替代基础搜索的实际后续贡献；冻结改进规则并过保护组后，再用已预选16图扩展。不得直接采用本轮筛选。
- 无运行中作业；SSH已关闭。无跨目录写入；无需B/C开始写新成绩。

## 接收确认（接收人填写并提交）

- 接收人 / 验收时间：待填。
- 实际检出SHA、验证命令与证据：待填。
- 结论及待补事项：待填，提交方不代填ACCEPTED。
