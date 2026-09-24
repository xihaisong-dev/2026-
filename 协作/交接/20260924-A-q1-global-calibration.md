# 交接：A-q1-global-calibration — 全局成本机制校准及24图验证

## 交付信息

- 本地任务：A-q1-global-calibration；Issue/PR：不适用，独立本地实验。
- 提交人/角色：Codex / A；接收人：用户及后续A操作者。
- 日期：2026-09-24（+08:00）。状态：READY，不代填人工验收。
- 分支：codex/q1-global-calibration，未推送。
- 产物提交SHA：9979706a64c028e585028f30e02c36d426032a89。
- 输入提交SHA：6022e1fbe6301d39c13b607ecc3359d1f8780a4a。
- 本机定位：C:/Users/Lenovo/.codex/worktrees/q1-structure-seeds/2026华为杯数学建模。
- 官方输入包SHA256：3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9；processed逐文件哈希由report.verify核对。
- 冻结实验输入SHA256：4beb0c46c73f9f5522814cde9b8e547e3b7ef2384c47bfdfa8b855e83f25a5be。
- 证据ZIP SHA256：eba7145f8e331e5ef8177b7cf628dd324a7ab1afddfae46d790ea9620e1af0e0。

## 已完成与产物

|路径|内容|版本|下游用途|
|---|---|---|---|
|图表/runs/20260924-A-q1-global-calibration|192次运行、计划、结果、搜索台账、复核谱系、源码快照及日志|本提交及provenance.json|复核原始证据|
|图表/runs/20260924-A-q1-global-calibration-analysis-v2|逐配置比较、预测误差和基础机会审计|采用v2|分析依据|
|审查/问题一全局成本校准协议_20260924.md及json|8图开发、16图扩展、预先冻结条件|开跑前冻结|防止事后挑例|
|程序/q1_opportunity.py、q1_experimental.py、q1_ablation.py|事件代理准入及被替代方案身份台账|本提交|实验配置，不改默认|
|程序/q1_global_calibration_report.py|哈希、预算、同候选池、同当前解及基础轨迹校验|本提交|可复核报告|

## 接手复现

- 依赖：Python标准库及经哈希核验的官方processed输入。服务器Python3.12.14；本机Python3.14。
- 服务器目录：/home/xihs/q1-campaigns/global-calibration-20260924-r01。
- 实际监督命令：`nohup /home/xihs/q1-runtime/python-3.12.14/bin/python3.12 -u launch.py > launch.log 2>&1 < /dev/null &`，launch.py已随证据保存。其执行95项unittest，再运行以下两批；完整参数数组另见execution.json。

```bash
/home/xihs/q1-runtime/python-3.12.14/bin/python3.12 -u 程序/q1_opportunity_campaign.py --reference-run references --output runs/development --workers 16 --variants routes_unguarded routes_event_guarded --cases case_058 case_039 case_072 case_009 case_100 case_040 case_028 case_067 --protocol 审查/问题一全局成本校准协议_20260924.md --verified-plan-runs /home/xihs/q1-campaigns/ranking-full100-20260924-r01/validation/图表/runs/20260924-A-q1-ranking-full100 /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_memory /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_hybrid
/home/xihs/q1-runtime/python-3.12.14/bin/python3.12 -u 程序/q1_opportunity_campaign.py --reference-run references --output runs/extension --workers 16 --variants routes_unguarded routes_event_guarded --cases case_010 case_021 case_026 case_027 case_035 case_043 case_044 case_046 case_054 case_057 case_068 case_078 case_079 case_083 case_097 case_098 --protocol 审查/问题一全局成本校准协议_20260924.md --verified-plan-runs /home/xihs/q1-campaigns/ranking-full100-20260924-r01/validation/图表/runs/20260924-A-q1-ranking-full100 /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_memory /home/xihs/q1-campaigns/memory-routing-20260924-r01/validation/runs/component_hybrid
```

- 上述真实命令均退出0，复跑须另建输出目录，不覆盖证据。引用输入目录对应前轮固定单核和原版验证；不复用搜索评分。
- 本机实际分析命令退出0：

```powershell
& 'C:/Users/Lenovo/AppData/Local/Programs/Python/Python314/python.exe' 程序/q1_global_calibration_report.py --run 图表/runs/20260924-A-q1-global-calibration --output 图表/runs/20260924-A-q1-global-calibration-analysis-v2
```

- output复跑须新目录。中间analysis版本未区分未评分提议与真实预算消耗，保留但应采用v2。
- seed0、2～5核、每配置12机会（11次新完整评分+1次固定单核引用）、四基础粒度。开发64次，扩展128次。
- 95测试通过；192份输入、冻结源、方案及结果核验通过；64次原版重算、128次严格历史原版复核复用。2112次全局搜索评分，156次事件代理额外核内准备，代理全局评分0。
- 1302个新证据文件的暂存Git blob字节哈希与磁盘相符，diff --check通过；计算结果/主程序/结果JSON存在且满足本轮最小产物尺寸。
- 正式阶段门禁：NOT_RUN，不改状态文件、main、默认或人工批准。

## 风险、接口和后续

- 本轮采用既有三轮Pipe依赖/DDR模块校准新路由准入，不改候选池内局部排序，不拟合逐case参数。它不是精确全局仿真、不是下界。
- 开发：1胜31平0负，合计时间下降0.010062%，搬运相同；MAPE11.2889%→1.6612%，准入24/30→30/30。
- 扩展：64组全平，时间与搬运均无新增收益；MAPE14.9676%→1.7732%，准入38/48→48/48。不可宣称泛化100%准确，也不是新的100图成绩。
- 028四核恢复17880cycles：未筛选10694242→筛选10676362。原随机迁移因依赖环不可行而不耗评分，新增评分挤掉后续有效local_reschedule；真实机会成本不在被替代动作的表面标签上。
- 未筛选新路由真实消耗78次机会：38个原可行评分、38个不可行试探、2个重复试探。可行评分中027四/五核两个有正直接前缀改善，各11517cycles；后续轨迹差异不能独立相加为因果收益。
- 额外准备使本批搜索耗时合计6219.343→7620.122秒，观测增加22.523%。16并发、背景负载变化，不能把它当稳定单机倍率。最大搜索445.207秒，含最终验证446.008秒，不含单核冷生成，不证明所有100图端到端达标。
- 保持实验开关，不替换默认。下一步先复用已准备核内依赖图降低开销，再冻结同候选池事件排序与局部排序对照，分离“准入改进”和“选到更好候选”的收益。
- 新字段：event_comparison；被替代plan hash、评分位置、incumbent hash等。报告consumed_score区分实际评分与仅提出但被筛掉的结构候选。
- 本轮影响建模报告、计算结果、代码清单及实验结果JSON，不派B自动改正式成绩。无运行中任务，服务器SSH已关闭。

## 接收确认（由接收人填写）

- 接收人/验收时间：待填。
- 实际检出SHA、验证命令与证据：待填。
- ACCEPTED / CHANGES_REQUESTED及待补项：待填，提交方不代填。
