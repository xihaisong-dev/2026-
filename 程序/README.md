# 计算实现

当前交付为问题一初版原型，不代表 FORMULATION / COMPUTATION 阶段完成，不用于直接派发正式论文写作。仅依赖 Python 3.10+ 标准库。

## 运行

在仓库根目录运行：

```powershell
python 程序/主程序.py prepare
python -m unittest discover -s 程序/tests -v
python 程序/主程序.py solve --cases case_001 case_093 --cores 2 4 --method greedy
python 程序/主程序.py solve --cases case_001 case_093 --cores 2 4 --method multilevel
python 程序/主程序.py solve --cases case_001 case_093 --cores 2 4 --method alns --budget 12 --seed 0
```

全量入口（耗时取决于候选评估次数）：

```powershell
python 程序/主程序.py solve --cases all --cores 2 3 4 5 --method alns --budget 12 --seed 0
```

可选第二轮优化：

```powershell
python 程序/主程序.py solve --cases case_001 case_093 case_034 --cores 2 4 --budget 4 --refine-budget 8
```

`--refine-budget` 默认 0，保持原有策略。开启后，在原有最优方案之外尝试 1/4、1/2、2 倍分组粒度，再根据官方时间线中耗时较长的 Task，尝试按主要 Pipe 工作量均衡拆分及迁移。改进后追加新瓶颈邻域，也保留未尝试的其他候选，最终只接受更优方案作为交付。此项预算单独计数，最多增加指定次数的官方评估；不是免费优化。开启后相对于同一次基础求解不会退步，但不保证优于把相同次数全部交给随机 ALNS。样本对照见 `计算结果.md`。

`prepare` 从仓库原始附件无损提取 code/data，逐图调用官方 validate_graph 并固化哈希；输入、配置和未修改的官方评估器保存在 `数据/processed/q1/`，可由原始 ZIP 重建，不随 Git 提交。已有导入仅核验，不覆盖。修改文件会导致求解拒绝启动。

每次运行创建独立的 `图表/runs/<时间>-A-q1/`，也可通过 `--output` 指定一个尚不存在的目录。逐算例输出：

- `*_plan.json`：官方接口的 node_to_subgraph 和 core_schedules，可直接交给附件问题一评估脚本。
- `*_evaluation.json`：官方完整结果，含时间线、流量、溢出和 DDR 竞争记录。
- `*_search.json`：随机种子、预算、候选评价和非法提案拒绝原因。
- `summary.json`：输入及代码哈希、各图指标、按图平均的加速比。仅全部成功才写 completed=true。

## 算法范围

- greedy：拓扑就绪集上的数据复用优先分组，加关键路径列表调度。`--block-size` 默认 64。缓存活跃集压力仅用于近似调度代价，不是精确溢出预测。
- multilevel：以 greedy 分组为起点，按张量超边通信量进行三层有向无环收缩，每层最多 32 次、合并块最多 1024 算子；逆向展开作近似代价细化。初版不是成熟超图划分库的完整替代。
- alns：以上两类初解择优，采用合并、拆分、边界移动、迁移和同核相邻交换五种操作，每个提案组合 1～3 次编辑；结构操作后重新调度，非法候选先拒绝，合法候选用官方评估器确认。算子权重随改进更新，允许模拟退火式接受，始终保留历史最优。初版破坏区域较小，尚未实现瓶颈驱动的大范围破坏策略。
- 三种方法均保留整图单 Task 兜底。核数为 1 时只运行官方同义单核基准，加速比固定为 1。
- `--budget` 仅限制 ALNS 新候选的官方评估次数，不包含至多三个初解；无足够合法新候选时允许提前停止。三方法的默认总评估成本不同，不能把默认运行当作同预算对擂。
- 核内 Pipe 顺序、地址依赖、溢出及带宽竞争完全由官方代码决定。近似成本只用于生成候选，不作为正式完成时间。

初版借鉴王朝闻（2022）的分支/子图调度、唐九飞等（2016）的融合与通信平衡、郑鎏韬（2025）的存储感知、肖星宇等（2026）的带宽与映射协同、许兆淳等（2026）的路径优先思想。没有复制论文中的硬件改造、算子重计算或动态执行周期校正。论文文件与完整索引见文献 PR #2；ALNS 是本题自行设计的组合求解器，不宣称直接复现某篇文献算法。

## 后续工作

完成 100 图 × 4 核数评测、等预算比较和消融后，再冻结参数与正式结果。当前初版不保证全局最优；大图完整官方时间线可能较大，搜索也会受评估成本限制。勿将原型测试数值直接写成全量实验结论。

## 文献启发的可消融实验框架

`q1_experimental.py` 不替换旧算法，使用 `--experimental` 显式启动：

```powershell
python 程序/主程序.py solve --cases case_034 --cores 4 --experimental --evaluation-budget 12 --features local_cost critical adaptive portfolio
python 程序/q1_ablation.py --cases case_001 case_093 case_034 --cores 4 --seeds 0 1 --evaluations 12
python 程序/q1_ablation.py --configs legacy_alns --cases case_001 case_093 case_034 --cores 4 --seeds 0 1 --evaluations 12
```

四个开关：

- `local_cost`：未观察子图补充内部计算依赖最长路径；已观察子图用官方 Step3 的独立 `local_makespan` 校准，按成员集合在本次求解内复用。缓存只对同一原图/配置/评估器有效，记录观测冲突数；不缓存并发 Task 时长，也不直接预测全局共享带宽时间。
- `critical`：冻结官方已观察 Task 时长，在数据依赖与同核顺序联合图上反推余量；优先处理低余量瓶颈。最优方案变化后立即刷新定向候选，不继续消耗旧队列。余量只作启发式，调整后仍重新仿真。
- `adaptive`：按区域主要 Pipe 工作量及数据驻留代理确定块边界，提供低搬运切点与局部合并候选。代理并非精确缓存峰值；原算子不会被重新切片或改写。
- `portfolio`：保留至多 4 个时间/额外搬运互补方案和部分不同结构，随机邻域可从不同父方案出发；UCB 为粒度、定向、随机和局部重调度分配探索机会。收益按归一化完成时间改善、尝试次数更新，不使用墙钟时间驱动选择，以保持种子可复现。Pareto 仅用于管理存档，不宣称安全剪枝或全局最优。

`--evaluation-budget` 是实验框架的**总官方调用次数**，包含单核兜底和初解，与旧 `--budget` 含义不同。非法或重复提案不消耗调用预算；有限尝试后仍未耗尽时明确报告 budget_exhausted=false，不能假装同预算。原版 ALNS 对照先确定其独特初解数量，再将剩余次数分给随机搜索。

默认消融包含 control、逐步加功能的四个配置，以及 full 分别去掉 local_cost / critical / adaptive；去掉 portfolio 与 local_critical_adaptive 相同，不重复运行。control 是新共同驱动器关闭四开关，**不是原版 ALNS**，所以另外运行 legacy_alns。

`q1_ablation.py` 每次创建新目录，每个实验保存 plan.json、search.json 和无损压缩的 evaluation.json.gz。summary.json 记录调用数、参数、输入/源码/产物哈希与逐次结果，最终检查 all_budgets_exhausted。

方法依据：仓库 paper 中 T10（§4.3，局部代价与多候选权衡）、IsoSched（§III-C，合并拆分与探索策略）等；以上是针对题目接口的启发式改造，不复现其核间直连、NoC 路由、抢占或层内切片，也不引入题面没有的硬件能力。实验功能仍需消融支持，不能因来自论文就默认开启。

本轮 54 次等预算运行中，`local_cost critical` 相对共同对照六组均改善，平均完成时间下降 1.274%；`adaptive` 在该组合上五组退步，完整组合不宜默认开启。当前建议试用以下组合，再扩大样本验证：

```powershell
python 程序/主程序.py solve --cases case_034 --cores 4 --experimental --evaluation-budget 12 --features local_cost critical
```

结果及限制见 `计算结果.md`。`q1_ablation_report.py --runs <实验目录> <旧算法对照目录> --output <新分析目录>` 会核对源码快照、产物哈希及配对预算，再生成描述性比较。旧运行的精确源码在各目录 source_snapshot 中保留；新运行自动保存源码快照。

## 插入式调度与通信优先级

在 `local_cost critical` 上可独立加 `insertion` 和 `comm_rank`：

```powershell
python 程序/主程序.py solve --cases case_034 --cores 4 --experimental --evaluation-budget 12 --features local_cost critical insertion comm_rank
python 程序/q1_ablation.py --configs local_critical insertion comm_rank insertion_rank
```

`insertion` 将就绪 Task 放入核队列中满足依赖的最早空隙，同时预留左右两侧的同核等待；不再只能追加到末尾。`comm_rank` 在向上优先级中用 `(same + (N-1)*cross)/N` 估计同步等待，实际选核仍按已分配核心逐依赖计算。该平均值是启发式，不代表实际跨核概率。两个开关都不免除 DDR 流量，官方评估器最终决定完成时间。关闭时仍走原调度器。

参考 [HEFT 原论文](https://ieeexplore.ieee.org/document/993206/) 的插入式 EFT 思路和 [公开 Python 实现](https://github.com/mackncheesiest/heft)；本项目独立实现题目适配逻辑，未复制第三方代码。原版 HEFT 的异构计算/边通信模型不能直接代替本题共享 DDR 仿真。另检索了 [dagP](https://github.com/GT-TDAlab/dagP) 与 [Multilevel Acyclic Hypergraph Partitioning](https://arxiv.org/abs/2002.02962)，本轮没有新增外部划分器依赖。

报告器可通过 `--pairs local_critical:insertion local_critical:comm_rank local_critical:insertion_rank` 指定比较；仍强制相同算例、核数、种子的配对和相同官方调用预算。新开关未加入默认八配置消融，避免悄悄改变旧实验含义。
