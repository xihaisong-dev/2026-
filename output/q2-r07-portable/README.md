# 问题二 r07 计算提交包

当前算法为结构准入加重复候选名额回收（r07），不是共享准备r08。
实测 Python 3.12.14；求解仅使用标准库。解压后在本目录执行：

```text
python verify_package.py
python 程序/q2_current_submit.py 数据/processed/q1/data/case_005.json -n 5 --migration 图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_005_multicore_res.json --output trial-005-5
python 程序/q2_current_submit.py 数据/processed/q1/data/case_001.json -n 2 --output cold-001-2
python 程序/q2_r07_reproduce.py --workers 1 --output reproduced-all
```

输出目录须不存在；核数支持1至5。每次输出标准`<case>_multicore_res.json`，只含node_to_subgraph和core_schedules，评价结果和搜索记录分开保存。
第一条求解命令使用冻结迁移种子复现正式100图实验。省略--migration可仅从原图运行：先执行额外12次A候选机会生成种子，再在B下重新评分并执行12次B机会（缓存命中也占机会），最后另做官方B回放。迁移种子耗时单列，不借用A的多核成绩。单核点使用规定整图基准，不优化分母。
批量复现可加`--cases 1 5 --cores 1 2 5`选取小样本；`--cold`从原图生成种子；并行前会检查本机资源。正式500点复现可能耗时较长，勿用小样本耗时外推。

图表/runs/20260924-A-q2-delivery-r07/包含500份标准方案（其中100份单核参考）、500行指标、100例宽表、五点PDF/PNG、LaTeX附录和编译预览。五点平均加速比为1、1.981113、2.815714、3.550822、4.159974，按100个逐图T1/Tk取算术平均。
相对r05为13胜387平0负；额外搬运合计增加0.028884%，必须如实披露。搜索时间不含预生成种子、单核分母、回放与审计；run.json另给本次端到端用时。

原始评估器和固定配置保持附件版本。包内manifest对所有文件校验；完整时间线保留在原运行证据，便携包带其逐文件哈希索引，省略体积较大的时间线。
此包完成问题二计算附件与写作材料交付，不代表整篇竞赛论文、匿名版式或人工验收已完成。正式图表嵌入后仍需B/C核对。
