# 交接：Q23-PRESERVED-R2B — 基础序列保护与低复制缓存

## 交付信息

- 提交A；接收后续A。2026-09-25（+08:00）；READY，仅表示本轮实验完成。
- 分支codex/q23-preserve-refill；产物提交f13ec2b535ba72893be4a31712d18a693ad74ef0；未推送。
- 本地C:/Users/Lenovo/.codex/worktrees/q123-manuscript。
- 输入版本承接5c6ed4fab62e3b59053b25a9903fdda0c9133b3d，固定数据/种子不变；新源码和输入哈希见图表/runs/20260925-A-q23-preserved-r2b/contract.json。
- 门禁NOT_RUN，未改状态源、默认入口、原500组或论文成绩；无新Issue。

## 实现与结果

程序/q23_preserved_trial.py：完整保留上一轮最多16个基础候选的顺序及评价机会，然后两臂均原版重放/内存审计并保存base_complete，再生成补充候选。补充去重后的空位回填后续基础候选，上限24。90秒暖启动预算包括所有生成、诊断及复核；不包含种子生成与固定T1。

程序/q23_preparation_reuse.py 新增SerializedPreparationReuse，miss直接存不可变pickle快照，hit还原隔离对象；完整输入键、进程内缓存、每次全局模拟不变。只反序列化本进程自产内存快照，非外部pickle。旧深复制实现保留作对照。

r2先验证候选规则和缓存；r2b增加基础阶段的已复核检查点后重跑相同20项。最终20项合法且官方重放一致，最长30.096秒；Q2六组与延长普通搜索持平，Q3三平一负。全部10组保住上一轮16基础候选的成绩，但不能保证优于继续普通搜索的24上限对照。044普通35703对新组合35975，仍暴露后8个机会的分配代价。

缓存四图真实不同候选流、三次轮换顺序计时，新快照相对原版耗时降低4.40%～33.80%，相对旧复制降低35.80%～42.84%。新快照192次完整结果一致，旧复制另192次一致。是求解器评价CPU耗时，不是NPU周期。缓存未启用到搜索对照中，不把微基准直接申报生产提速。

## 产物与复现

- 报告：图表/runs/20260925-A-q23-preserved-r2b/README.md、report.json。
- 规则首轮与缓存：图表/runs/20260925-A-q23-preserved-r2/。
- 最终检查点版本：图表/runs/20260925-A-q23-preserved-r2b/。
- 两份目录均保留run_preserved.py、preserved.log、contract.json及逐项完整评价。r2旧源码快照位于r2/sources。
- 服务器独立目录/home/xihs/q1-campaigns/20260925-q23-preserved-r2和-r2b；已全部结束，不需重启。
- 服务器Python：/home/xihs/q1-runtime/run-python。原实际命令均为 `nohup /home/xihs/q1-runtime/run-python -u run_preserved.py > preserved.log 2>&1 < /dev/null &`。r2b等待r2微基准完成后才开始，避免两批互扰。

本机验证命令：

```sh
python -m unittest discover -s 程序/tests -p test_q23_preparation_reuse.py -v
python 程序/q23_preserved_report.py 图表/runs
```

本机和服务器各5测试通过；报告断言核对全部旧基础序列、检查点存在、最终不差于基础检查点；Q3/044本机与服务器最终完整字段一致（双方均跑完候选池，非不同预算性能比较）。结果包408份文件哈希核验见r2b/result_hashes.json。

## 接手决策

不启动新100图，不默认推广关键候选。下一步若继续，优先研究普通候选后的独立追加机会及低成本生成，避免固定名额继续挤掉优质普通候选。缓存可以作为明确的实验开关进一步在大图和真实搜索中验证；不能宣称全量收益或冷启动10分钟已合规。

本轮仍是历史小样本开发证据，未见图泛化和全量生产缓存验证NOT_RUN。接收人自行填写接收结论，未代填ACCEPTED。
