# 交接：Q1 全100图五核 — 已启动，等待完成

## 交付信息

- 本地编号：Q1-FULL100-5CORES；用户最新范围：先运行最新完整组合的五核加速比，不运行其他核数。
- 提交人/接收人：A / 后续A操作者；日期：2026-09-25（+08:00）。
- 状态：DRAFT / RUNNING，不能据此更新正式全量成绩。
- 分支：codex/q1-full-staged-analysis；冻结包提交：309b11d5；算法基于3dd41178，运行器精确版本由contract.sources固化。
- 本机worktree：C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 远程：xihs@120.27.220.233:9022，主机iceda；密码未写入文件。
- 远程目录：/home/xihs/q1-campaigns/20260925-q1-full100-5cores。
- PID：3812；runtime：/home/xihs/q1-runtime/run-python（Python3.12.14）。

## 冻结合同

100张原图、5核、完整组合full、seed0，每个配置590秒上限，16个独立工作进程。使用原有经验证整图单核计分分母；不重算单核，不跨方案逐图事后择优。旧正式基线五核平均加速比3.6659026939。当前基线搜索预算不同，只比较结果质量，不声称同求解时间因果收益。

包：output/q1-full100-5cores-20260925.zip，SHA256：75516309454d5892a14d90dc1a3b964a6188aa985690e2fec7ac2b55422dc475。235文件、17933245字节。服务器解包后已核验包、源码、输入和配置哈希。兼容性071/5核/20秒试跑原版复核通过，耗时15.607秒，结果13705；这是兼容性诊断，不充当100图中的正式结果。

## 当前进度快照

服务器2026-09-25 15:16:53：已启动16，完成0，运行16，排队84，16个运行图均已有原版官方核验的保底方案。运行器仍存活；CPU负载约13，服务器20逻辑CPU，启动时约94GiB可用内存。快照会过期，后续必须重新读取服务器文件。

本地目录：图表/runs/20260925-A-q1-full100-5cores。包含contract.json、package.json、deployment.json、汇总器两项测试日志。不得在本机启动相同任务造成重叠。

## 查看与接手

在上述远程目录执行：

```bash
/home/xihs/q1-runtime/run-python 程序/q1_full_staged.py report --output 图表/runs/20260925-A-q1-full100-5cores
tail -5 图表/runs/20260925-A-q1-full100-5cores/launcher.log
ps -p 3812 -o pid,etime,stat
```

原启动命令：

```bash
nohup /home/xihs/q1-runtime/run-python 程序/q1_full_staged.py launch --workers 16 --output 图表/runs/20260925-A-q1-full100-5cores > 图表/runs/20260925-A-q1-full100-5cores/launcher.log 2>&1 < /dev/null &
```

不要重复执行启动命令；launcher.lock防止重叠协调器。正常退出会移除锁。未完成目录不覆盖、不自动重算；失败记录保留，修复必须另列实验，不得静默选择更好的重跑结果。

## 完成后的工作

1. 确认summary.complete=true、finished=valid=100、failed为空；覆盖恰为case001～100的5核full。
2. 下载rows、summary、execution、contract及各任务最终verified对应plan/evaluation，核对SHA。candidate不是已核验最终结果。
3. 计算mean(T1_i/T5_i)，单独计算总周期、总额外搬运量、胜平负、端到端耗时；未完成样本均值不能报为全量值。
4. 分析退步结构和超时/保底回退；至少抽取改进与退步方案独立复核。全量证据确认前不更新正文数字或main默认方案。
5. 所有图已参与以往研发，这一轮是全量回归，不是未见图泛化证明。

正式结果门禁NOT_RUN；工作流阶段未更改。接收人未填写验收结论。
