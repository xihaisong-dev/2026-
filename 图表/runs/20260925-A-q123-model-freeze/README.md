# 三问定版与复现

权威模型说明在建模报告.md顶部。freeze.json固定源码、输入、初解和最终方案字节哈希；不改历史算法、不把实验结果逐case混选。状态MODEL_AND_ALGORITHM_FROZEN，submit_ready=false。

- Q1：routes_gate_reuse，100图×1～5核，入口q1_submit.py，预算12、种子0、counter后端、最终原版重放。
- Q2：protected＋GenerationReuse，最新100图×5核，入口q23_portfolio_reuse.py --problem 2 --reuse。
- Q3：combined＋GenerationReuse，最新100图×5核，入口q23_portfolio_reuse.py --problem 3 --reuse。
- Q2/Q3：590秒、384提议、20%最终复核预留；排序准备复用和收益/尝试次数权重关闭。自适应分配仍依赖实际耗时，不承诺不同硬件候选序列相同。

## 复现示例

在包的根目录，以Python3.12运行，输出目录必须不存在。case001仅示例；正式逐图命令和对应初解见全量rows/*.json。

```sh
python 程序/q1_submit.py 数据/processed/q1/data/case_001.json -n 5 --budget 12 --seed 0 --backend counter --verify-final --output trial_q1
python 程序/q23_portfolio_reuse.py --problem 2 --graph 数据/processed/q1/data/case_001.json --migration 图表/runs/20260924-A-q1-delivery-r02/solutions/5cores/case_001_multicore_res.json --output trial_q2 --cores 5 --seconds 590 --seed 0 --max-proposals 384 --reuse
python 程序/q23_portfolio_reuse.py --problem 3 --graph 数据/processed/q1/data/case_001.json --seed-plan 图表/runs/20260925-A-q2-new-seeds/5cores/case_001_multicore_res.json --anchor 图表/runs/20260924-A-q3-full-r02/case_001/5/case_001_multicore_res.json --output trial_q3 --cores 5 --seconds 590 --seed 0 --max-proposals 384 --reuse
```

## 写作边界

沿用固定单核参考，平均加速比逐图比值取算术平均；总周期和额外COPY bytes独立列出。不能把Q3/Q2不同方案的周期比解释为纯硬件Cache加速比。

Q2/Q3最新五核不得与旧版1～4核拼成统一新算法曲线。补齐最新低核数、Q3最终方案无L2评价、冷启动耗时和论文附件一致性后再做提交验收。正式门禁NOT_RUN。

冻结包包含源码、官方处理后输入、固定初解、Q1全部方案和Q2/Q3最终结果；完整搜索轨迹另存output/q23-full100-verified-evidence.zip，SHA见冻结清单。原始全轨迹不全展开进入Git，本地最终方案可直接官方重放。
