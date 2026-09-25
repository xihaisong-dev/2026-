# 交接：Q2-FULL100 — 五核100图两臂对照已部署

## 交付信息

- 任务来源：用户要求完成开跑前检查，并在服务器运行问题二五核100case。
- A端提交，后续A计算操作者接收；2026-09-25，READY（运行交接，非结果验收）。
- 分支：codex/q2-full100-fivecore；未推送GitHub，无PR。
- 部署证据SHA：604174b3748054f1f0dbb05028f1b08ad9722163；冻结执行源码SHA：7e719f53。
- 本地目录：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 阶段/门禁：NOT_RUN，状态文件和正式500组输出未改。

## 冻结范围与实况

100个case，全部五核，ordinary_extended与protected各100次，共200次。每项seed=0、590秒求解截止、最多96次提议；相同Q1迁移种子。合同列出全部输入、种子、源码和官方配置哈希，单核分母固定，原正式结果仅作比较，算法不读取其成绩。

服务器iceda，独立目录：/home/xihs/q1-campaigns/20260925-q2-full100-5cores。
运行目录：图表/runs/20260925-A-q2-full100-5cores；启动PID：7085。
已确认四个预检子任务正在运行：067/072 × ordinary_extended/protected，并已各自保存原版官方验证的回退方案。当前尚未生成preflight.json，不能宣称预检完成。

程序先4并发完成预检及独立官方审计；四项有效且<=600秒才自动启动其余196项，按照即时CPU/内存余量最多16并发。预检直接计入冻结200项，不重复计算。预检不通过将停止扩展并保留日志，不静默忽略失败。

暖启动求解计时包括加载、生成、官方评价、checkpoint落盘；不包括预生成种子、固定T1及独立审计，审计耗时另列。所有最终checkpoint本身已经是原版官方评价，独立审计再次比较全部字段。

## 产物与验证

- 程序/q2_full_timed.py：冻结、哈希检查、条件放行、任务去重、恢复校验、独立审计、按臂汇总。
- 程序/tests/test_q2_full_timed.py：实际强制中断保留有效官方checkpoint；拒绝复用损坏结果。本机及服务器各2项均通过。
- 图表/runs/20260925-A-q2-full100-5cores/contract.json：200任务清单及合同；deployment.json记录真实启动方式。
- output/q2-full100-20260925.zip：396文件，17548372字节；SHA256 63d383f67f00febb0e305626a2383a0bd2ad262b403d1d4469fd8d7dc17679b7。
- 服务器396文件逐项哈希校验及冻结输入检查通过。凭据未写入包或仓库。

## 查看进度

在已授权SSH连接后：

```text
cd /home/xihs/q1-campaigns/20260925-q2-full100-5cores
/home/xihs/q1-runtime/run-python 程序/q2_full_timed.py report --output 图表/runs/20260925-A-q2-full100-5cores
tail -20 图表/runs/20260925-A-q2-full100-5cores/launcher.log
```

检查preflight.json的passed、full_launch.json的实际并发，以及rows/*.json。
summary.json中每臂complete只有有效100项才为true；部分样本均值不得叫全量成绩。失败项必须单列，不能填零或删除分母。pairs.json只比较双方均有效的同case，不能逐图挑臂拼正式成绩。

## 恢复与后续

不要启动第二个协调器。若发生中断，先检查launcher.lock对应进程及所有子任务是否仍活跃；未确认停止不能移除锁。完成行恢复前校验计划/评价文件哈希。失败记录保持可见，未完成目录不被覆盖；需要重跑时另建显式补跑批次并保留失败原因，不能悄悄增加一臂预算。

结束后下载rows、summary、pairs、preflight及全部最终方案/官方评价，核对200项身份、有效数量及冻结哈希。分别报告两臂官方算术平均加速比、总周期、额外搬运、胜平负、最差退步、求解/独立审计时间及失败率。正式均值目前仍为4.159974，不自动采用挑战者。

原问题一批次未修改；该批次的后续状态请读其独立目录。未启动B/C或代填人工验收。接收确认由接收人填写。
