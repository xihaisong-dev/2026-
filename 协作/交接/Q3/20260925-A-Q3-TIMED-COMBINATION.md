# 交接：Q3-TIMED-COMBINATION — 五核组合优化与全量验证

## 交付信息

- 本地编号：Q3-TIMED-COMBINATION；无对应新 Issue。
- 提交人：A；接收人：后续 A 操作者，结果确认后再派 B 写作。
- 日期：2026-09-25（+08:00）。状态 READY，仅指实现及样本证据，不代表全量计算完成。
- 分支：codex/q3-timed-combination；未新建PR、未推送。
- 产物提交 SHA：ea0c725508cd7c9c937500e1777c2babff1f5881。
- 冻结执行源码 SHA：d3eca5b7e69d0b2a3d0399138fa2ebd3c1a90d59。
- 本地 worktree：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 正式阶段与门禁：NOT_RUN，未更改状态/工作流状态.json。
- 输入来源及哈希：图表/runs/20260925-A-q3-combination-full100/contract.json；新问题二种子 manifest 位于 图表/runs/20260925-A-q2-new-seeds/5cores/manifest.json。

## 已完成与产物

| 路径 | 内容 | 用途 |
|---|---|---|
| 程序/q3_timed_combination.py | 限时候选搜索、官方L2评分、检查点 | 新实验求解入口 |
| 程序/q3_combination_campaign.py | 冻结、配对试验、条件扩量、独立复核 | 五核100图验证 |
| 审查/问题三五核限时组合_20260925.md | 模型差异、时间口径、样本结果 | 分析与写作边界 |
| 图表/runs/20260925-A-q3-combination-full100/ | 合同、18项样本结果与轨迹、门槛、跨平台复核 | 可追溯样本证据 |
| output/q3-combination-20260925.zip | 本地可重建部署包，未纳入Git | SHA256 f4de2a11e22817cae736668c3f88e799f2c799f7e052a38abe35f4fb08d597b2 |

样本9图为005、032、039、044、046、048、064、071、088，均五核。原Q3/新起点local/combined平均加速比为2.920196/3.061814/3.064884，总周期718223/693472/691121。combined对local为2胜4平3负，周期下降0.339%，逻辑额外搬运上升21.452%。不可把初解继承收益全归因于新组合，也不可把样本成绩当全100成绩。

本机新测试2项、既有FIFO测试3项通过；服务器新测试2项通过。18项官方全字段重放、FIFO及物理内存审计通过，032组合Windows跨平台完整重放通过。最终方案的无L2评价也已保存。

## 正在运行

- SSH：xihs@120.27.220.233:9022。凭据不存文件。
- 根目录：/home/xihs/q1-campaigns/20260925-q3-combination。
- Python：/home/xihs/q1-runtime/run-python（系统python3不可替代）。
- 启动PID：31162；状态锁 launcher.lock。
- 9图18项试验门槛通过后，剩余91图combined已自动启动，16并发。最后一次检查18项完成、34个作业目录，表示16项扩量作业已启动；这不是实时进度保证。
- 输出：图表/runs/20260925-A-q3-combination-full100。
- 总计109项，即100项combined+9项local；不做逐图事后择优拼接。

## 复现与接手

在上述服务器根目录执行：

```sh
/home/xihs/q1-runtime/run-python 程序/q3_combination_campaign.py check --output 图表/runs/20260925-A-q3-combination-full100
/home/xihs/q1-runtime/run-python 程序/q3_combination_campaign.py report --output 图表/runs/20260925-A-q3-combination-full100
tail -20 图表/runs/20260925-A-q3-combination-full100/launcher.log
```

启动命令已实际执行，切勿重复运行：

```sh
nohup /home/xihs/q1-runtime/run-python 程序/q3_combination_campaign.py launch --workers 16 --output 图表/runs/20260925-A-q3-combination-full100 > 图表/runs/20260925-A-q3-combination-full100/launcher.log 2>&1 < /dev/null &
```

固定五核、590秒暖启动上限、96提议、随机种子0；只读FIFO容量与带宽以合同为准。独立复核另计，不宣称冷启动端到端十分钟。重复方案去重、官方完整结果精确匹配，无数值容差放宽。

下一步：检查进程和逐项失败日志，等待100项combined全部独立验证完成，再回收行记录、方案及完整评价；比较相同100图官方算术平均加速比、总周期、逻辑额外搬运与求解时间。旧Q3五核参考均值4.240374854733234、总周期64562282。若有失败明确列出，不能当作完整100图成绩。保留1～4核旧证据，不宣称本轮已重新验证500组。

## 风险与限制

- 原默认提交入口、原500组、论文正式成绩未替换。
- 样本门槛只说明值得扩量；组合仅略优于local，且搬运上升，需要全量判断。
- 依赖预生成问题二/旧问题三种子；生成这些输入及固定T1的时间不包含在590秒中。
- 服务器还有其他任务，勿终止不属于本批的进程。
- 冻结后不修改正在执行的源码、合同或阈值。需要改动则另起版本和目录。
- 接收结论由接收人填写，提交者未代填。
