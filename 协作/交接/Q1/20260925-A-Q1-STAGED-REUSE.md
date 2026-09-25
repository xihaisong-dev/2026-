# 交接：Q1-STAGED-REUSE — Task准备复用与分阶段搜索

## 交付信息

- 本地任务：Q1-STAGED-REUSE，用户直接授权；Issue不适用。
- 提交人：A；接收人：下一轮A求解操作者。
- 日期：2026-09-25（+08:00）；状态：READY（开发证据，不是正式全量验收）。
- 分支：codex/q1-staged-reuse；产物提交：6a7d58b7；首版负结果快照：54d8c5cb；输入：20376dcc。
- Worktree：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 输入来源：数据/processed/q1，q1_io.verify校验原附件；每次contract记录图和源码哈希，报告有最终源码清单。
- 阶段与门禁：延续问题一优化开发，不改变正式阶段；100图同版本新成绩门禁NOT_RUN。

## 产物与结论

|路径|内容与用途|
|---|---|
|程序/q1_task_reuse.py|逐Task完整局部图键，核内准备复用，全局DDR与依赖每次重算|
|程序/q1_staged_portfolio.py|独立进程阶段限时、未用复核预算回收、官方复核后导出|
|程序/q1_staged_moves.py|结构先验、最多12任务的实际释放链修复|
|程序/q1_staged_experiment.py|60秒四方法对照|
|图表/runs/20260925-A-q1-staged-report/|报告、机器可读指标、源码哈希、复现说明|

第一版缓存因深复制变慢；修正版在固定36次候选评分池上更快，完整字段一致。结果有明确局限：结构先验和时间线修复不是所有图都有效，不得全部默认合并进原提交算法。

072五核最后4768050 cycles，比上一轮限时4831281降低1.308783%，含两次原版复核500.656秒。067完整组合13351488、保守组合13320614均仍逊于上一轮最好13292569。记录全部退步，不能逐case事后择优当正式自动选择器。

## 复现与检查

沿用仓库Python环境及已校验官方数据；输出目录必须不存在。

```powershell
python 程序/q1_staged_portfolio.py 数据/processed/q1/data/case_072.json -n 5 --seconds 590 --output 图表/runs/new-q1-staged-072
python 程序/q1_staged_portfolio.py 数据/processed/q1/data/case_032.json -n 5 --seconds 60 --no-structure --no-timeline --output 图表/runs/new-q1-reuse-032
python 程序/q1_staged_experiment.py --cases 32 88 --cores 5 --seconds 60 --workers 2 --output 图表/runs/new-q1-ablation
python 程序/q1_timed_verify.py --runs 图表/runs/new-q1-staged-072 --output 图表/runs/new-q1-staged-072-replay.json
```

实际单测：test_q1_task_reuse.py 5项、test_q1_staged_moves.py 2项、test_q1_fast_evaluator.py 3项、test_q1_staged_checkpoint.py 2项，共12项通过。日志在staged-ablation与staged-report。两轮小图四方法共24项，全部退出码0、输出合法且未超过限时；5份代表性结果另做独立原版完整重放，见staged-ablation/independent_replay.json。

固定种子不能保证跨硬件墙钟搜索路径相同；保存方案完整官方重放应相同。固定候选池测速包含特意重复第二遍，不代表正常搜索的命中率。原型源文件通过Git两版快照与各contract追踪，不得混称一个冻结版本的正式全量对照。

## 接口、风险和下一步

- 最终输出为 verified 指针对应方案以及 case_XXX_multicore_res.json；candidate只是加速评估候选，不能提交。
- 每次等价全局评估都是评分调用；不能作为免费代理隐去预算。初始、search/search2、复核阶段均有独立记录。
- 10分钟单位是case×核数，不含重算固定整图单核计分基准或额外独立审计。当前大图测试通过，不保证所有图/机器都能在保底期限内取得首个方案。
- 本轮五核实测，不能声称2～5核100图全面受益。原q1_submit、正式500配置及论文数字未替换。
- 下一步优先减弱无效结构先验对预算的持续占用，保护基础邻域，再用未调参图与其他核数验证；按图选算法必须由预先固定结构规则实现，不能记case编号。
- 受影响目录：程序/、本轮图表/runs/、计算结果.md、此交接；B/C目前无需更新正式结果。
- B/C派稿前仍需更广的固定版本验证与A重新出具证据包。

## 接收确认

由接收人填写，提交方未代填验收结论。
