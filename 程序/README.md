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
