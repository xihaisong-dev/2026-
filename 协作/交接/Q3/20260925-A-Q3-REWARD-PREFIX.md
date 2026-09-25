# 交接：Q3-REWARD-PREFIX — 不依赖实际耗时的候选权重

## 交付信息

- A交后续A；2026-09-25（+08:00）；READY。无新Issue/PR，未推送。
- 分支codex/q3-deterministic-weights；产物提交525cd234；输入b41a331。
- 本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript；服务器/home/xihs/q1-campaigns/20260925-q3-reward-prefix。
- 原始输入及源码哈希见证据目录contract.json与server_source_inputs.json；280原始文件下载和Git索引字节哈希均通过。
- 正式门禁NOT_RUN；未变更工作流阶段。冻结codex/q23-submit-freeze（ebce54dd）及原protected/combined入口不变。

## 已完成与产物

程序/q23_reward_prefix.py保留基础候选前缀，追加阶段50%固定探索、50%按结构先验乘以每次尝试平均改善奖励抽样。权重不读取墙钟；重复、无效、耗尽及拒绝均计入尝试。独立固定选择种子，原官方评价和字典序接受规则不变。

证据目录：图表/runs/20260925-A-q3-reward-prefix。README.md、report.json、validation.json为汇总；rows记录逐项真实命令，jobs与ablation_null保存方案、官方结果、轨迹；hashes.json固定原始证据。

三图005/044/072，Q3五核，旧组合/固定轮转/收益权重/收益权重加准备复用四臂，共12项，全部官方完整重放与审计通过。统一590秒、384提议上限、种子0、20%最终复核预留。另做005奖励关闭控制一项，通过。

- 005旧组合42856→42541 cycles（−0.7350%），搬运1706228→1701492 bytes；固定轮转43163→42541（−1.4410%）。
- 044为35982、072为4771746，均持平。一胜两平不等于全量提升。
- 005奖励关闭42721→42541，奖励开启再减少180 cycles与1920 bytes，两臂均384提议；主实验与补充控制负载不同，不作统计显著性声明。
- 准备复用开关共同803提议和481完整评价哈希一致；54基础提议保护通过；评分481→482，最终质量持平。准备复用未贡献本轮最终周期收益。
- 最长外部墙钟479.450秒、峰值子进程RSS906.40MiB；暖初解历史不计，不宣称全量冷启动十分钟满足。

## 接手复现

服务器Python3.12.14，入口/home/xihs/q1-runtime/run-python。运行命令：

```sh
nohup /home/xihs/q1-runtime/run-python -u run_reward_prefix.py > reward_prefix.log 2>&1 < /dev/null &
python -m unittest discover -s 程序/tests -p test_q23_reward_prefix.py -v
python 程序/q3_reward_prefix_report.py 图表/runs/20260925-A-q3-reward-prefix
```

逐项worker真实命令见rows/*.json.command；奖励关闭入口程序/q3_reward_null.py，参数见ablation_null/summary.json.arguments及ablation_contract.json。复跑换新输出目录，不能覆盖证据。

本机2项测试3.093秒，服务器2项4.150秒；报告重放每一步权重、奖励与选择，errors为空。最小产物检查、git diff --cached --check、280原始文件Git索引哈希通过。正式门禁NOT_RUN。

## 风险、接口和后续

实验新增独立入口，不替换冻结版，不改变正式成绩。单种子三图，005为已知退步图，不能证明泛化。奖励关闭控制details.policy继承包装标签；实际策略由summary.arguments.ablation、合同及选择权重重放确认，报告已显式说明。

决策：保留实验。下一步在未参与规则选择的图、多种子中按相同时间预算验证，再决定是否全量运行。无需继续增加算子。接收人需自行核对产物SHA、复跑报告；未代填ACCEPTED。无待用户解除阻塞。
