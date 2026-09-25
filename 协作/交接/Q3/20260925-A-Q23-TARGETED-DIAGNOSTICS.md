# 交接：Q23-TARGETED-DIAGNOSTICS — 预算诊断与小试验拒绝推广

## 交付信息

- 提交角色A，接收人为后续A；不派B改写正式成绩。
- 时间2026-09-25（+08:00）；状态READY（诊断和小试验证据），不是正式门禁通过。
- 分支codex/q23-budget-diagnostics；产物提交5c6ed4fab62e3b59053b25a9903fdda0c9133b3d；未推送。
- 本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 本地任务号Q23-TARGETED-DIAGNOSTICS，无新Issue。输入为上一轮Q2两臂200项、Q3组合100项及9项对照的实际日志；图输入继承审计processed目录。
- 源文件/种子哈希：图表/runs/20260925-A-q23-diagnostics/trial_contract.json；导入190份服务器产物哈希：同目录q23_result_hashes.json。
- 阶段与门禁：NOT_RUN，未修改状态源、旧默认入口或正式500组。

## 产物与结论

- 程序/q23_log_diagnosis.py：历史逐类别收益、耗时、重复率、共同搜索前缀。
- 程序/q23_targeted_candidates.py、q23_targeted_trial.py：Q2保护8基础候选后的关键等待修复、Q3固定划分/归属的缓存顺序修复，统一90秒含最终原版复核。
- 程序/q23_preparation_reuse.py：进程内按完整输入复用核内准备，每次仍完整全局模拟，未接入正式入口。
- 程序/q23_targeted_report.py：报告生成。
- 图表/runs/20260925-A-q23-diagnostics/README.md、diagnosis.json、trial_summary.json：完整结论；logs保留历史证据，trials保留20项小试验及4个复用微基准。

Q2历史退步16图的joint有效评价851→379，新增类别813.40秒仅直接贡献679周期改善；观察证据支持预算机会成本，但不能宣称反事实因果分解。历史重复0秒漏计生成/哈希成本，Q3未评分提议无法分开重复与邻域耗尽。

小试验Q2六图0胜5平1负，Q3四图1胜1平2负，均未满足事前扩量标准。20项含最终原版重放和实际物理内存审计全部通过，最长19.941秒，Q3还通过FIFO核验。未发现新增等周期减搬运接受动作。

56次实际候选完整字段比较一致；复用冷批次耗时增加11.5%～56.2%，同池暖缓存才节省3.0%～13.4%，不能用重复池命中率代表去重搜索。缓存体积上限按序列化大小32MiB，不是进程RAM上限。默认不启用，不推广到100图。

## 实际命令与运行

服务器根目录/home/xihs/q1-campaigns/20260925-q23-targeted；Python为/home/xihs/q1-runtime/run-python。全部完成，无需重启。实际启动命令：

```sh
nohup /home/xihs/q1-runtime/run-python -u run_targeted.py > targeted.log 2>&1 < /dev/null &
```

run_targeted.py已复制到本批证据目录；4并发20个小试验，随后串行4份微基准（每份两次独立冷缓存重复）。退出码及输出见targeted.log。复用对照固定原版先、复用后，未随机化执行顺序，耗时仅作诊断。

本机验证命令（Python可替换为已安装标准库环境）：

```sh
python -m unittest discover -s 程序/tests -p test_q23_preparation_reuse.py -v
python 程序/q23_log_diagnosis.py 图表/runs/20260925-A-q23-diagnostics
python 程序/q23_targeted_report.py 图表/runs/20260925-A-q23-diagnostics
```

本机与服务器各2项单测通过；Q2/065和Q3/044本机30秒冒烟与服务器90秒试验均跑完候选池，最终评价完整字段一致。不是不同时间预算的收益比较。源码变化后应新建输出，不能覆盖本次结果。

## 接手重点与限制

1. 不新增100图批次、不更新论文全量成绩。上一轮全量成绩不变。
2. 后续先保留完整基础序列，对关键候选去重后的空缺回填普通候选。本轮033被替换的基础候选仍有价值；Q3/044、046仅得到1个关键候选，筛选过窄。
3. 降低准备缓存的快照复制开销，使用不重复的真实候选流、交替计时顺序验证，再谈生产收益。
4. 暖启动初解与固定T1预生成不含在90秒中；小样本不能证明冷启动100图端到端十分钟。样本为历史图，不称未见图泛化。
5. 报告脚本为下游生成工具，新增后不改变已运行trial_contract中的算法源码哈希。

接收确认由接收操作者填写；未代填ACCEPTED。
