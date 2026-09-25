# 交接：Q23-ORDER-PREPARE — 排序内部不变准备复用

## 交付信息

- 本地编号Q23-ORDER-PREPARE，A交后续A，2026-09-25（+08:00），READY；无新Issue/PR，未推送。
- 分支codex/q23-order-prepare；产物提交9d94b5b09acdce9d2c28c80ffe196e5c2db5e646；输入703133d6。
- 本机C:/Users/Lenovo/.codex/worktrees/q123-manuscript；服务器/home/xihs/q1-campaigns/20260925-q23-order-prepare。
- 冻结提交codex/q23-submit-freeze（ebce54dd）不变。正式阶段门禁NOT_RUN，未更新状态源及正式成绩。

## 已完成与产物

程序/q23_order_prepare.py新增独立OrderingPreparation：在同一不可变图作用域，以完整有序mapping为键，缓存依赖结构、rank、预整理张量信息；owners、counts、live/resident、ready堆每次重建。保留旧GenerationReuse，准备缓存另设32MiB序列化负载上限，实际RSS另测。原q2_solver、protected/combined及正式入口均未修改。

程序/q23_order_portfolio.py包装完整组合；两臂保留生成复用，仅新臂启用排序准备。程序/q23_order_prepare_bench.py、q23_order_prepare_ablation.py、q23_order_prepare_stress.py分别运行三图固定工作量、三臂消融和细粒度压力测试；q23_order_prepare_report.py汇总。证据目录图表/runs/20260925-A-q23-order-prepare。

1. 两项本机单测通过（2.663秒）：多种划分、映射、窗口、权重、优先级的输出一致；结果隔离与补丁退出恢复；完整Q2/Q3实验入口经原版重放一致。
2. 初始三图双臂固定工作量排序耗时下降22.92%/26.39%/34.40%，不代表全求解时间或NPU周期。三臂消融表明纯缓存增量仅9.97%/6.83%/−0.40%，部分收益来自避免循环内重复张量拆解。
3. case072细化至29666个单操作子图，4变体×2重复，输出完全一致，整体排序时间下降15.36%，缓存增量7.06%。此压力划分未作正式评分/提交，不能当作官方结果。
4. 完整Q2/Q3各case072五核两臂，共4项、590秒、种子0、96次提议、20%最终复核预留。均经原版评价及物理审计；45共同方案官方完整结果哈希一致；最长499.643秒，峰值子进程RSS923.66MiB。
5. **Q2退步**：评分25→29，周期4768866→4795907，增加27041（0.567%），搬运增加7354256字节。Q3周期4771746和搬运均持平，评分30→30。
6. Q2准备缓存命中44/51次，但实际耗时影响保护窗口和收益/耗时权重，joint 5→7、packing 2→7、frontier 3→1。两臂先取得4811152周期方案，基线后续order得4768866，新臂packing得4795907；核查基线最终方案未进入新臂评分池。

结论：局部计算加速正确且有收益，但当前完整组合质量不能保证；不推广、不覆盖冻结提交，不扩大全100图。74服务器原始文件、12本地固定工作量文件的Git索引字节哈希验证通过，303服务器源码/输入与本机一致。程序/code_manifest.json、图表/全部结果.json、计算结果.md登记本轮。

## 接手复现

服务器Python3.12.14及/home/xihs/q1-runtime/run-python依赖环境。已执行：

```sh
nohup /home/xihs/q1-runtime/run-python -u run_order_prepare.py > order_prepare.log 2>&1 < /dev/null &
```

启动脚本及日志归档，真实逐项命令在rows/*.json.command；新建输出目录复跑，不覆盖原证据。

本机已执行且退出码0：

```sh
python -m unittest discover -s 程序/tests -p 'test_q23_order*.py' -v
python 程序/q23_order_prepare_bench.py --output 图表/runs/20260925-A-q23-order-prepare
python 程序/q23_order_prepare_ablation.py --output 图表/runs/20260925-A-q23-order-prepare/ablation
python 程序/q23_order_prepare_stress.py --output 图表/runs/20260925-A-q23-order-prepare/stress
python 程序/q23_order_prepare_report.py 图表/runs/20260925-A-q23-order-prepare
python -m py_compile 程序/q23_order_prepare.py 程序/q23_order_portfolio.py 程序/q23_order_prepare_report.py
```

上述三个计算命令当前目录已存在，复跑必须换新目录；报告可对既有证据复算。contract/validation/source_inputs中含源文件哈希，results包含初解和图哈希。最小产物校验和git diff --cached --check通过；正式门禁NOT_RUN。

## 风险与后续

- 下一步先固定基础候选机会和顺序，避免缓存后瞬时耗时改变基础序列；再利用节省时间追加探索，另做同预算实验。
- 本轮不修改自适应策略掩盖负结果。单种子、少量图、微秒级短测试可能含噪声，未证明统计显著性、全量收益或冷启动十分钟达标。
- 导入初解历史生成时间不计；未更新1～5核正式500配置及论文分数。
- 缓存要求图在作用域内不可变，私有准备结构不可对外暴露或修改；不能把缓存旧全局时长混入实现。
- 无需用户解除的阻塞项。接收方自行填写验收结论，未代填ACCEPTED。
