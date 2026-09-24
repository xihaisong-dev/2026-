# 计算实现

> **2026-09-24 当前采用版本：r02 / routes_gate_reuse。** 本文保留研发历史，写作以 `审查/问题一交付与赛题要求核对_r02.md` 和 `协作/交接/Q1/Q1-WRITE-r02.md` 为当前入口。单图运行 `python 程序/q1_submit.py 数据/processed/q1/data/case_001.json -n 5 --output trial --verify-final`；批量运行 `python 程序/q1_reproduce.py --output all100 --workers 2`。输入尚未导入时先运行 `python 程序/主程序.py prepare`。当前程序包 `output/q1-delivery-r02-20260924-portable.zip`，校验后再运行。1～5核平均加速比：1、1.834917、2.546238、3.161009、3.665903。只报告我们自身工程；旧历史段落不是当前提交口径。


## 当前复现入口与全量基线

当前分支为 `codex/q1-delivery-runtime`。比赛复现入口为 `q1_submit.py`，固定采用已完成100图官方评测的 `shared_region`，种子0、预算12；历史 `主程序.py solve` 的默认旧算法不代表这个基线。

```powershell
python 程序/q1_submit.py 数据/processed/q1/data/case_001.json -n 5 --output output/q1-example --verify-final
python 程序/q1_reproduce.py --output output/q1-full-reproduction --workers 2
```

输出目录必须不存在。单图入口接受任意合法图JSON及 `--config`，输出 `<case>_multicore_res.json`，仅含题目要求的两个字段；评价、搜索历史、配置与哈希另存。1核使用整图固定基准，2～5核使用同一启发式配置。全量入口每图只算一次单核基准，均值严格按逐图加速比求算术平均。完整运行仅需Python标准库；绘图脚本另需matplotlib。

默认 `--backend counter` 使用哈希锁定的官方源码派生后端：Task剩余操作计数、预建张量反向索引；Step1/2/3、共享DDR更新、同步规则均不变，官方原件不修改。搜索中的基础代理成本按子图成员缓存，每次仍应用最新局部观测，缓存上限8192组。完整全局仿真继续计入12次评价机会；增加 `--verify-final` 会另做一次原官方复核，并单独记录耗时。`--backend official` 可回到原实现，不开启上述加速。具体一致性验证范围与运行时间以本轮报告为准，不能把评估器加速等同于比赛Makespan下降。

第十八轮100图基线1～5核平均加速比：1、1.700388600754181、2.264697028017020、2.685511275068951、2.9906610645949363。固定单核和400份多核官方结果见 `图表/runs/20260923-A-q1-v18-merged`。新初始划分对400组为23胜206平171负，未晋升为默认。

## 第十七轮历史结果

当前分支 `codex/q1-pipe-event-chain`。主目标与约束继承下文模型，新增逐算子/Pipe/内存依赖的固定三轮DDR事件近似，仅传播受依赖影响的延迟；它不是官方全局精确模拟，也不是下界。关键链候选联合合并、核心迁移和局部顺序修复，每次最多12提案、2或3个Task、512算子，保持无环；可选后置策略保护四档划分和早期随机机会，在最后一次官方评价执行修复。

6图006/017/040/045/048/065，2～5核，种子0/1，每配置48组、每组12次官方评价。基线 `shared_region` 4136008 cycles；`shared_event` 4135313；`shared_event_chain` 4133765；`shared_event_late` 4127509，后者下降0.205488%，23胜20平5负。额外搬运64366926→64201414 bytes，下降0.257138%。原 `shared_exact` 为4136380。

共240次完整运行/2880官方评价；废止批次另有已知120调用及未知在途调用，未计入比较。4进程并行、62测试通过；同官方次数而非同墙钟预算，全部是开发集，无独立泛化证据，不替换默认。代码、逐组退步、完整命令及预算边界见[第十七轮报告](../审查/问题一第十七轮事件依赖与关键链验证.md)。旧五图截图不与本轮六图混算。

## 第十六轮历史建模与评测范围

第十六轮历史分支：`codex/q1-ddr-phase-rank`。第十六轮算法/结果产物提交 `2d715556b5c1bc03251d128ac57cd7c906adafea`，实验不替换默认方案。根目录主程序的默认策略与下列显式实验配置不是同义词。

### 建模

问题一是有依赖、缓存约束和共享带宽竞争的多核划分—映射—排序组合优化。原图的非COPY算子组成DAG，张量连接生产者与多个消费者；划分P决定每个算子属于哪个Task，映射m决定Task在哪个核执行，各核序列π决定任务顺序。

主目标是最小化官方模拟返回的总完成时间T(P,m,π)；时间相同时以额外搬运字节数B_added作为次级择优，按(T,B_added)字典序比较。T不是算子周期简单相加，也不等于通信边数乘固定等待；每个候选的正式结果由未改动的官方评估器给出。

约束与机制：每个非COPY算子恰好分配一次；划分后的商图、加上同核执行顺序的图必须无环；每核串行执行Task，核内四条Pipe可按依赖重叠；跨核前驱完成后等待1000 cycles，同核前一Task完成后等待100 cycles，多个释放条件取最大值。DDR共享60 bytes/cycle，L1/UB容量分别524288/131072 bytes，超容量影响由官方溢出与内存复用依赖处理。不同Task即使同核也不自动免除边界搬运；共享输入收益主要由子图融合后真实COPY/溢出变化决定。以上参数来自附件当前配置。

这是以离散决策加事件模拟评估求解的原型，不是已求得全局最优的整数规划结果。启发式成本只是候选生成/排序代理，不能当作精确目标或可靠下界。

### 算法

1. 整图单Task兜底；贪心融合＋关键路径列表调度生成初解，再尝试有向超图粗化。当前实现是自研有界启发式，不冒称完整复现成熟超图划分库。
2. 共享输入感知合并，四档基础划分机会保护；定向、随机、重调度搜索有明确调用预算，重复方案以哈希和评价ID留证。
3. 有界关键区域修复调整局部划分与映射/顺序；官方总预算内保留最好结果。自适应扩区、多步最好前缀等为可选消融，不是默认全部叠加。
4. 本轮对照 `shared_region`（区域基线）、`shared_exact`（官方核内准备时长重排）、`shared_phase`（最多64个核内DDR阶段的并发近似）。后两者仅修改候选排序，完整官方评价仍每次搜索12次。阶段法冻结计算重叠，不能精确反映全局逐Pipe推进，已保留负结果。
5. `q1_parallel.py` 将独立case/core/seed/config交给进程池，各运行独立输出，父进程汇总；并发改变评测吞吐，不改变硬件核数模型或搜索预算。

### 实际计算了哪些case

最新一轮为下列6图，每图2/3/4/5核、随机种子0/1、三个算法配置，共6×4×2×3=144次求解、1728次官方完整评价；4个电脑工作进程完成，批次约246.21秒。

| case | 原图算子数（含COPY） | 参与划分的非COPY算子数 |
| --- | ---: | ---: |
| case_006 | 851 | 678 |
| case_017 | 1758 | 1373 |
| case_040 | 3381 | 3083 |
| case_045 | 1787 | 1651 |
| case_048 | 1900 | 1728 |
| case_065 | 914 | 704 |

原来截图的五图为017、045、048、065、077；本轮没有077，不可混用平均值。附件共有100图，读取/校验100图不等于完成100图×全部核数的优化求解。本轮不含单核对照重算。

每配置48点汇总：区域基线4136008 cycles，局部精确4136380，DDR阶段4136655。阶段法对区域基线1胜45平2负，总时间增加0.015643%，不推广。58项测试通过，16个与历史串行实验重合的结果一致。

详见[第十六轮报告](../审查/问题一第十六轮DDR阶段与并行验证.md)、[完整结果](../图表/runs/20260923-A-q1-v16-parallel/summary.json)和[按核心对照](../图表/runs/20260923-A-q1-v16-analysis/comparison.json)。具体复现命令在报告中，复跑须选新输出目录。


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

## 瓶颈前瞻与结构下界

可选 `lookahead` 在四个低余量瓶颈 Task 上按主导Pipe负载的1/4、1/2、3/4切点试构造至多12种拆分，并以代理完成时间排序；候选仍由官方评价计入总调用预算，构造与排序会额外占用CPU时间。第五轮同预算结果四胜四负，不默认开启。

```powershell
python 程序/q1_ablation.py --cases case_001 case_093 case_078 case_034 --seeds 0 1 --configs insertion_rank lookahead
python 程序/q1_ablation_report.py --runs <实验目录> --pairs insertion_rank:lookahead --bounds --output <新分析目录>
```

`--bounds` 核验本地输入后计算不可删除的非COPY算子Pipe工作量/核数与计算依赖最长路径下界；不包含预测等待、额外搬运或溢出。下界不保证可达。报告中的时间/下界不是实际次优程度的证明。审核报告的逐项复核见 `审查/问题一初版审核复核.md`。

## 时间诊断、联合邻域、预算与结果缓存

所有实验候选在官方评价前记录固定方案预测，评价后记录独立Task时长回放。`local_model_residual` 是回放与预测的差，包含Pipe依赖、复制、内存约束等；`global_replay_residual` 是官方时间与独立回放的差，可提示并发影响，不能单独证明全部由DDR造成。两项相加等于预测总误差。`fixed_profile_wait_effect` 在固定独立时长下关闭等待后重放，是同步影响的反事实代理，不能额外与前两项相加。逐候选数据见search.json。

新增四个独立开关：

- `calibrated`：以已经评价的独立Task时长/原成本比例，按主导Pipe分别取最近64个不同子图观测的中位数，校准未观察子图；比例截断0.5～4，保留计算关键路径下限。仅用本次求解过去的观测，不使用当前候选真值预测自己。已观察子图继续复用精确独立时长。
- `joint`：对低余量瓶颈联合生成主导Pipe拆分、边界算子双向移动后重新映射，以及核心迁移；合法候选按完整固定方案时间代理排序。
- `budget_adapt`：将拆分、边界移动、迁移、重排分成独立搜索臂，按过去实际完成时间改进/尝试数选择，四分之一提案机会保留轮转探索。非法/重复提案也计入尝试数以反映无效生成成本；不是按墙钟实时调节。
- `ddr`：从实际DDR竞争事件与Task并发时长相对独立时长的增量识别候选对象，尝试迁移、合法核内相邻重排。它不强制传输串行，也不直接修改官方时间；收益须重新仿真。

```powershell
python 程序/q1_ablation.py --configs insertion_rank calibrated joint_cal budget_joint all_new --seeds 0
python 程序/主程序.py solve --cases case_001 --cores 4 --experimental --evaluation-budget 12 --features local_cost critical insertion comm_rank calibrated joint --cache-dir _tmp/q1-evaluation-cache
```

`--cache-dir` 可选，默认关闭。缓存键覆盖原图、硬件/等待配置、整个官方Python评估源码集合、Python版本和完整方案；结果带校验哈希、gzip压缩、临时文件原子落盘，损坏报错。缓存不信任人工编辑的数据。不要把私人缓存目录作为正式成绩。命中仍占一个候选名额，不增加搜索预算；日志分别给出 `official_calls` 与 `cache_hits`，二者相加为候选评价数。关闭缓存时与先前总官方调用预算一致。跨实验复用只节约求解时间，不直接改变Task执行时间。

当前是可消融原型，四项联合并不保证优于原算法。正式实验应关闭缓存，或同时报告真实调用与缓存命中，不把命中冒充重新仿真。默认full及旧八配置消融不包含这些新开关。

## 分层覆盖与保留基础搜索预算

`q1_structure.py --output <新目录>` 核验并统计全部100图，按算子数排名分四层，以规模、计算关键路径占比、张量字节/计算周期、最大扇出四个维度归一化后选择距层内中位数最近的未调参图；只用结构，不用求解成绩。profile.json固定算法源码哈希、输入哈希、核数2～5、种子0、预算12、关闭缓存及每运行90秒上限。仅四个代表不能覆盖全部极端结构。

`q1_stratified_run.py --profile <profile.json> --output <新目录>` 按该协议运行，最多两个子进程；超时终止单次运行，保留日志及不完整目录，不填写完成时间。batch.json区分实验已结束与所有求解均成功。comparison.json只纳入双方完成的配对，并列出被排除项；幸存配对可能存在规模偏差，不能外推到全部100图。墙钟超时受机器负载影响，不是算法不可解的证明。

新开关 `guarded_joint` 与基础 `local_cost critical insertion comm_rank` 配合。前ceil(0.75×候选预算)次评价保持基础搜索行为，只收集校准信息；之后开启成本校准，并每四个提案机会引入一次联合候选。不可与旧calibrated/joint/portfolio等提前改变搜索的开关混用。保留前段历史最好解，但不保证胜过同总预算全部用于基础搜索的结果。若预算12，保护的是前9次，不能宣称完整保留基础12次结果。

```powershell
python 程序/q1_structure.py --output 图表/runs/<新结构目录>
python 程序/q1_stratified_run.py --profile 图表/runs/<新结构目录>/profile.json --output 图表/runs/<新评测目录>
python 程序/q1_ablation.py --configs insertion_rank guarded_joint --cases case_001 case_093 --cores 4 --seeds 1
```

本轮另按全部结构统计选择计算关键路径占比最大、张量字节/工作量最大两图作补充，名单在其求解前保存为独立profile；这是顺序开展的探索，不是事前注册的统计验证。实验期间不修改已冻结的求解文件。


## 同一划分的束搜索映射（第八轮，可选）

```powershell
python 程序/主程序.py solve --cases case_045 --cores 2 3 4 5 --experimental --evaluation-budget 12 --features local_cost critical insertion comm_rank beam
python 程序/q1_ablation.py --cases case_045 --cores 2 3 4 5 --seeds 0 --evaluations 12 --configs insertion_rank beam
```

beam宽度8、最大128个Task，超过阈值回退insertion_rank；固定任务优先顺序，只扩展核心与插入位置。比较原映射代理后择优，实际成绩仍由原始官方评估器决定。不会增加单次官方评价预算，但耗费更多候选构造时间。尚未验证稳定收益，尤其4/5核没有稳定改善，不默认开启，也不建议与guarded_joint组合解释前缀保护。

q1_placement_probe.py用于事后固定划分诊断：先从既有官方结果读精确局部时长，再生成映射，额外评价单独计数；不属于同预算求解性能。其CLI参数见--help，结果见计算结果.md第八轮。


## 精确全局重映射后处理（第九轮，可选）

```powershell
python 程序/q1_exact_polish.py --runs 图表/runs/20260923-A-q1-v8-beam --config beam --extra-evaluations 8 --output 图表/runs/新的精修目录
```

输入为q1_ablation.py的完整实验目录。原始12候选方案之外追加至多8候选，最终完整官方复核额外一次；不是保持原12候选预算。完整mapping缓存仅复用局部准备工作，仍模拟动态DDR，且保持Task编号。旧CLI与默认算法不变。

q1_exact_report.py比较额外精修与直接加长搜索，只纳入候选总数相同的组合；最终复核开销另列。当前等20候选实验精修总体慢0.343%，不推荐替换主搜索。官方私有接口变更需重新做差分测试，禁止直接声称跨版本缓存安全。


## 划分机会保护、共享输入、局部修复（第十轮）

```powershell
python 程序/q1_ablation.py --cases case_045 --cores 2 3 4 5 --seeds 0 --evaluations 12 --configs insertion_rank partition_guard shared_input local_repair
python 程序/主程序.py solve --cases case_044 --cores 4 --experimental --evaluation-budget 12 --features local_cost critical insertion comm_rank partition_guard shared_input
```

partition_guard保持旧轮转顺序，在剩余预算即将不足时预留未尝试的四档粒度。最小预算8；不等于四个不同合法候选，不保证不退步。shared_input和local_repair都要求partition_guard，不能把仅在这一预算机制上测出的效果推广为对任意搜索都有效。

shared_input只改变multilevel候选：考虑无内部生产者的共享输入复用，扣除计算并行损失代理，并限制合并规模及全图代理不恶化。真实候选仍官方评价。local_repair保留未受影响Task的核和相对顺序，非法修复拒绝；子Task继承父核可能抑制并行，当前不默认推荐。新配置均为独立消融，默认组合不变。

q1_partition_report.py核验预算、四档尝试和初始前缀；--baseline-runs仅提取经校验的insertion_rank历史行，报告调用合计包含复用参考，不能当成本轮新增调用。v10a前置所有粒度的失败与v10b修订均保留，见计算结果.md第十轮。


## 有界局部重分配（第十一轮，实验开关）

```powershell
python 程序/q1_ablation.py --cases case_045 --cores 4 5 --seeds 0 --evaluations 12 --configs shared_input shared_repair_move
```

repair_move要求partition_guard，不能与local_repair同时启用。最多2个受影响Task×2个候选目标核×1个插入位置，加全局和继承候选，每次编辑至多6个代理方案。保留全局代理兜底，实际评价总预算不变。当前28组总计只少7 cycles，不能视为稳定收益，因此默认不启用。所有结果和反例见计算结果.md第十一轮。


## 第十二轮：固定关键区域破坏—贪心修复（实验开关）

`shared_region` 配置继承 `shared_input`，新增 `region` 特性。最多选择4个在数据依赖/同核相邻关系上连接的Task、512个算子；以冻结官方时间线余量选择种子。仅生成原划分、少量均衡再划分和高关联边界移动，最多6种映射，每种按关键尾长/任务时长两种优先级进行贪心调度，最多12个代理候选，不枚举分区、核心组合或排列。区域外核心归属和相对顺序不变，时间可以变化。商图与核心顺序必须无环。

最终B版在第二次或之后的随机提案机会使用一次区域候选，恢复原有local_reschedule；partition_guard继续保留四档grain构造机会。每次求解最多一次区域提案，可能因重复或非法而没有新增官方调用。仍是12个总候选预算，包含初解，不能保证完整保留原搜索轨迹或在每组上不退步。A版占用local_reschedule的失败结果也保留；默认配置未改变。

```powershell
python 程序/q1_ablation.py --cases case_017 case_045 case_048 case_065 case_077 --cores 2 3 4 5 --seeds 0 --evaluations 12 --configs shared_region --output 图表/runs/请改成全新目录
```

结果和限制见 `审查/问题一第十二轮区域修复验证.md`；这是已反复使用的开发集，不能作为独立泛化证据。


## 第十三轮：区域空隙插入（未默认启用）

`shared_region_gap` 在 `shared_region` 上只增加 `region_gap`，将区域重建的核心队尾追加改为最早可行空隙插入，复用本仓库 `q1_insertion.earliest_gap`，保留间隙两侧同核等待、跨核释放及区域外核心/顺序约束。参考HEFT与mrocklin/heft的算法机制，未复制外部代码、未引入依赖。候选上限12、区域4任务/512算子、一次区域搜索机会、12次总官方评估均不变。

实验 `20260923-A-q1-v13-*` 包含28组原回归，以及预先固定的新图006/064/090/040、2/5核、种子0/1，基础/区域/空隙三配置对照。原回归空隙版最终时间与区域版全部持平；不得将已有区域方案的改善归因于新插入改动。完整文献矩阵、结果与局限见 `审查/问题一第十三轮文献与空隙修复验证.md`。


## 第十四轮：冻结排序审计、DDR代理与边界细化

- `q1_frozen_audit.py --runs <已有运行目录...> --output <新目录>`：从已验证当前方案重建仅含当前方案局部观察的成本快照；不冒称恢复历史完整状态。所有候选评分在官方新评估前计算，保存状态哈希、计划和官方结果；审计评估次数单独计数。
- `shared_fluid`：原区域池按冻结的粗粒度共享DDR代理重排；边界数据量均匀摊到Task时间，按聚合需求超过带宽时的减速做事件跳跃。系数仅由已评当前方案拟合到[0,2]，不能解释为DDR因果归因，尚未描述突发COPY和溢出阶段。
- `shared_refine`：不启用DDR修正，仅增加至多3步×每步4个边界移动探测，每步保留代理严格改善且无环的方案，保持区域外划分、核心和相对顺序。
- `shared_fluid_refine`：组合两项。最多24次区域重建/15个保留候选，仍只有一次区域官方提案机会，总官方预算12；代理开销增大，不等于相同墙钟预算。原默认不变。

所有增强依赖region与partition_guard；为独立消融，本轮不与region_gap组合。运行方式例如：

```powershell
python 程序/q1_ablation.py --cases case_017 case_045 case_048 case_065 --cores 2 5 --seeds 0 --evaluations 12 --configs shared_fluid shared_refine shared_fluid_refine --output 图表/runs/请使用新目录
```

结果及限制见 `审查/问题一第十四轮冻结成本与边界细化验证.md`。


第十五轮新增 `shared_exact`、`shared_exact_wide`、`shared_exact_uphill` 消融配置。局部准备复用官方边界/溢出/Pipe逻辑，不计作全局评价；额外耗时单列。基础粒度 `protected_grain_ledger` 明确记录新评估或重复引用；`q1_local_rank_audit.py` 审计固定池，`q1_ranking_report.py` 校验台账及配对结果。详见[验证报告](../审查/问题一第十五轮排序与区域验证.md)，均未成为默认。


第十六轮新增 `shared_phase` DDR阶段排序实验开关，未推广。`q1_parallel.py --workers 4` 将独立case/core/seed/config分配到多进程，每运行独立目录、父进程统一汇总；可调workers但须留内存余量。完整命令及负结果见[并行验证](../审查/问题一第十六轮DDR阶段与并行验证.md)。


## 结构初解同预算对照

`q1_structural_seeds.py` 构造完整弱分量、分量分批与深度窗口初解；对应消融配置为 `seed_components`、`seed_batches`、`seed_depth`、`seed_combined`。正式默认配置不变。`q1_seed_campaign.py` 固定十图、12 评价机会、种子和原版 A 最终重放；所有输出目录必须是新目录。主实验 200 组，稳健性 40 组。基础输入先按原有 prepare 流程准备，并保留 v18 的已校验固定单核结果。

```powershell
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/q1-seed-reproduce-primary --workers 12
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/q1-seed-reproduce-robust --workers 4 --robustness
python 程序/q1_seed_report.py --primary 图表/runs/q1-seed-reproduce-primary --robustness 图表/runs/q1-seed-reproduce-robust --prior 图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv --output 图表/runs/q1-seed-reproduce-analysis
```

平均加速比按每图单核/多核比值取算术平均。求解耗时与模拟出的 makespan 单位不同；本轮本机和服务器分片的运行耗时不能直接用来声称算法墙钟加速。停止进程前先保留完整记录；迁移时冻结任务清单，只派发未完成任务，候选评分预算不会因续跑而增加。


## 完整分量预算控制实验

`component_guard` 与 `component_slot` 继承 `shared_region`，只允许一份经结构筛选的完整分量候选，不启用深度窗口/分批。前者在初解阶段评分，后者替换一次普通随机扰动。结构门槛不满足则保留原搜索。固定预算 12，测试输出必须为新目录。

```powershell
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/component-reproduce-primary --workers 12 --variants shared_region component_guard component_slot --cases case_017 case_045 case_048 case_065 case_077 case_002 case_028 case_063 case_067 case_085 case_006 case_040 case_090 case_097 --protocol 审查/问题一分量预算优化实验协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/component-reproduce-robust --workers 4 --variants shared_region component_guard component_slot --robustness --protocol 审查/问题一分量预算优化实验协议_20260924.md
python 程序/q1_component_report.py --primary 图表/runs/component-reproduce-primary --robustness 图表/runs/component-reproduce-robust --previous 图表/runs/20260923-A-q1-structural-seeds --prior 图表/runs/20260923-A-q1-v18-analysis/all_case_results.csv --output 图表/runs/component-reproduce-analysis
```

`q1_seed_campaign.py` 新增可选 `--cases/--variants/--cores/--seeds/--protocol`，不传仍为原结构初解矩阵。正式 `q1_submit.py` 默认不变。原版 A 的最终复核开销与搜索秒数分开记录。


## 首次改善后解锁第二布局

实验配置 `component_followup` 在 `component_slot` 首次结构候选严格降低 Makespan 后，才允许评估另一份节点分组不同的完整分量布局。总预算仍为 12；第二评分只占普通随机或已评估等价方案的重复机会，没有机会就跳过。最多两次结构评分，官方接口和正式默认不变。

```powershell
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/followup-reproduce-primary --workers 12 --variants component_slot component_followup --cases case_017 case_045 case_048 case_065 case_077 case_002 case_028 case_063 case_067 case_085 case_006 case_040 case_090 case_097 --protocol 审查/问题一条件第二布局实验协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/followup-reproduce-robust --workers 4 --variants component_slot component_followup --robustness --protocol 审查/问题一条件第二布局实验协议_20260924.md
```

输出目录须为新目录；保留固定单核与原版最终复核。报告程序 `q1_followup_report.py` 的 `--help` 列出本轮、上轮和历史结构实验的对照输入。不要用单核总时间/多核总时间替代逐用例平均加速比。


## 冻结局部排序全量实验

`component_local_rank` 在已有完整分量池内使用独立官方局部准备排序；不运行完整共享DDR模拟，仍限制12次评价机会，正式提交入口默认未改。

```powershell
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/ranking-reproduce-full100 --workers 16 --variants component_local_rank --protocol 审查/问题一排序诊断与全量验证协议_20260924.md --cases (1..100 | ForEach-Object { 'case_{0:D3}' -f $_ })
```

输出必须为新目录。完整审计与验证命令在 `图表/runs/20260924-A-q1-ranking-execution/full_execution.json` 和 `audit_command.json`；服务器绝对路径按本机工作目录调整。分析脚本 `q1_ranking_full_report.py --help` 列出所需历史对照和冻结证据；绘图脚本使用可选matplotlib，不属于求解器依赖。


## 内存路由和主导分量实验

新增可选配置 `component_memory`、`component_hybrid`，分别只替换原内存拒绝路由、主导分量拒绝路由，保护基础预算。`component_fast` 只加速成环检查，保持上一轮解质量。默认均不变；不按case编号选择算法。memory存在保护组退步，不能直接全局采用。

```powershell
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/memory-reproduce --workers 6 --variants component_memory --cases case_058 case_039 case_072 case_028 case_067 --protocol 审查/问题一内存路由与主导分量验证协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/hybrid-reproduce --workers 6 --variants component_hybrid --cases case_009 case_100 case_040 case_028 case_067 --protocol 审查/问题一内存路由与主导分量验证协议_20260924.md
python 程序/q1_seed_campaign.py --reference-run 图表/runs/20260923-A-q1-v18-merged --output 图表/runs/fast-reproduce --workers 4 --variants component_fast --cases case_091 --protocol 审查/问题一内存路由与主导分量验证协议_20260924.md
```

目录必须新建。上述fast命令会额外重复原版最终复核，耗时不在已报告搜索秒数内；本轮的精确结果复用基准脚本为q1_contraction_benchmark.py，服务器执行命令与输入包哈希见memory-routing/execution_metadata.json。报告命令见交接单；90测试命令为 `python -m unittest discover -s 程序/tests -p "test_q1*.py"`。


### 候选机会成本实验（未采用）

`routes_unguarded`按结构启用memory/hybrid路由及等价收缩加速；`routes_guarded`追加同口径局部时长筛选。32组开发检验0胜30平2负，筛选有误拒且未消除保护组退步，保持实验开关，正式默认不变。

`q1_opportunity_campaign.py`支持`--verified-plan-runs`，只复用已原版复核的同输入、同配置、同方案字节、同完整结果的最终验证；搜索评分不复用。`q1_opportunity_report.py`核查哈希、预算和历史同池候选，并保留失败。

复核命令（output须新目录）：
```powershell
python 程序/q1_opportunity_report.py --run 图表/runs/20260924-A-q1-opportunity-budget --output _tmp/opportunity-review
```
冻结启动命令及参数：`图表/runs/20260924-A-q1-opportunity-budget/launch.py`、`execution.json`。16图扩展因开发门槛失败未运行。


### 全局成本机制校准实验

`routes_event_guarded`继承`routes_unguarded`候选池及排序，以固定三轮Pipe/依赖/DDR回放比较候选与当前解。每次比较两次核内准备、0次全局评分，耗时记录于`event_comparison`。95项测试通过，开发32组1胜31平，扩展64组全平；不替换默认。新增被替代方案hash、评分位置及已有精确评分编号，可区分不可行/重复试探与真正消耗的基础评分。

```powershell
python 程序/q1_global_calibration_report.py --run 图表/runs/20260924-A-q1-global-calibration --output _tmp/global-calibration-review
```

output必须不存在。正式批次完整命令、冻结源与日志见该run的`execution.json`、`launch.py`和`runs/*/source_snapshot`。报告以`global-calibration-analysis-v2`为准，中间版尚未将未评分提议从实际预算消耗中区分。


## 问题二当前main首轮原型

输入必须由当前原始附件经 q1_io 审计。目录名 q1 不代表共享场景A评分。`q2_submit.py graph.json -n 4 --migration Q1_plan.json --output new_dir` 提供标准输出；迁移计划可省略，使用合法整图回退。候选始终由官方B重新评价，固定单核分母默认用Q1已验证的精确计数引擎重新计算，`--reference-backend official` 可用原入口核对。没有复用A多核成绩。

`--mode base|ordinary|guided` 分别为8基础机会、基础加4普通J、基础加4诊断J；guided仍在首轮验证，不视为已采用。`q2_main_campaign.py freeze|development|validation|scale` 为固定协议入口；大图使用 `q2_large_campaign.py scale --case 14` 等执行补充协议，仅加速等价单核分母。相同输出不覆盖；输入、配置、官方版本和完整计划共同限定B缓存。

差异和模型见问题分析.md、建模报告.md末尾；每组search.json区分迁移、结构候选、J、命中及实际官方调用。task执行cycles、额外搬运bytes和求解seconds严格分开。Q1冻结源码及成绩保持不变。


### Q2 r03 隔离对照

`python 程序/q2_controls_campaign.py freeze` 冻结新实验；`run --phase development --case 12` 等运行单图；`report` 汇总全部120份方案；`python 程序/q2_controls_finalize.py` 格式化并索引。运行目录固定为20260924-A-q2-controls-r03且禁止覆盖，复现需独立副本/新版本OUT。placement两组8机会，J三组12机会，各类内同预算；不将两类预算混作因果对照。完整来源和版本见contract.json及source_manifest.json。


### Q2 r04 审计与结构准入

`q2_requirements_audit.py`只读核查历史方案并另存标准名样本导出；当前OUT-v2已存在，复现须新目录。`q2_route_campaign.py freeze`冻结，`run --phase development --case 12`等运行，`report`汇总；`q2_route_finalize.py`登记证据。每组12机会，路由仅可替换第7/8机会，J仍普通4次。所有输出禁止覆盖，当前默认q2_submit未改。


### Q2 r05 全量复现

新入口`q2_r05_submit.py`读取固定全量决策；传入`--migration`复现共同预生成种子的对照，省略时从原图生成Q1种子并单独记录额外12次A机会及耗时。旧`q2_submit.py`默认保持历史版本。完整命令和时间口径见`output/q2-r05-portable/README.md`，先运行包内`verify_package.py`。全量800结果、400选定方案容量核验及500行指标见`图表/runs/20260924-A-q2-full-r05/`。


### Q2 当前入口 r07

当前计算交付切换到`q2_current_submit.py`；单例支持-n 1至5及可选--migration。批量入口`q2_r07_reproduce.py`默认100图×1至5核，--workers 1串行；输出须新目录。完整命令、冷启动与冻结种子口径见`output/q2-r07-portable/README.md`，包内先运行verify_package.py。历史入口与结果保留。
