# 通用神经网络处理器多核调度完整复现包

本项目对应题目三个问题，包含100个原始用例、未修改的官方评估程序、确定性候选生成算法、最终调度方案、完整评估结果、绘图代码及论文生成代码。算法不需要GPU，不涉及深度学习训练。

## 1 安装环境

推荐在Windows的Anaconda Prompt或PowerShell中进入本目录，然后运行：

```powershell
conda env create -f environment.yml
conda activate npu-scheduling
```

也可以仅安装Python依赖：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux/macOS激活命令为 `source .venv/bin/activate`。调度和官方评估仅依赖Python标准库；NumPy、Pandas、Matplotlib用于结果分析与绘图。重新生成Word还需要Pandoc，Conda环境文件已经包含它；仅使用pip时需自行安装Pandoc。Word打开与使用已交付的论文不需要Pandoc。

绘图优先使用中文字体Noto Sans CJK SC，也兼容Windows常见中文字体。若本机缺少全部中文字体，请先安装思源黑体或Noto CJK，避免图内中文显示为方框。正式图已经包含PNG、SVG和PDF版本。

## 2 直接查看已有结果

无需重新运算即可查看：

| 路径 | 内容 |
|---|---|
| `results/results.csv` | 100用例×5核数×3场景的1500条最终结果 |
| `results/summary.json` | 每问、每个核数的汇总统计 |
| `results/dataset_features.csv` | 100个用例的结构特征 |
| `results/plans/` | 官方格式调度方案，每份仅包含规定的两个字段 |
| `results/official_results/` | 官方完整结果，JSON以gzip无损压缩保存 |
| `results/baselines/` | 官方整图单核基准及其计算时间 |
| `results/candidates/` | 逐候选评估指标、失败原因与方案哈希 |
| `results/certificates/` | 证书评分路径使用的逐候选有效偏序等价证书；仅该路径生成 |
| `results/validation_report.json` | 独立核验结果 |
| `figures/` | 论文图片与对应绘图数据 |
| `paper.md` | 已填入本次计算结果的论文源文稿 |
| `paper_template.md` | 使用占位符连接实算结果的文稿模板 |
| `official/` | 随题提供的原始评估脚本 |
| `data/` | 原始计算图与固定config.txt |

解压某份完整评估JSON的方法：

```powershell
python -c "import gzip,pathlib; p=pathlib.Path('results/official_results/case_019_p2_n5.json.gz'); p.with_suffix('').write_bytes(gzip.decompress(p.read_bytes()))"
```

论文附录按用例与核数给出全部结果；CSV与JSON保留程序原始精度。

## 3 生成一个用例的调度方案

```powershell
python src/solver.py data/case_019.json -n 5 --problem 2 --config data/config.txt -o outputs/case_019_multicore_res.json
```

此命令使用官方模拟选择候选，另存候选搜索记录。`--problem`可取1、2、3；但论文第三问主实验特意复用第二问胜出方案，以隔离Cache硬件效果，单独运行problem3重新选优的数值不属于论文成对实验。

只生成完整分量均衡方案、暂不搜索：

```powershell
python src/solver.py data/case_019.json -n 5 --problem 2 --generate-only -o outputs/case_019_multicore_res.json
```

该快速模式保持完整弱连通分量；对单个巨大分量的图可能只用到一个核心，不保证得到与完整候选搜索相同的性能。

使用原始官方入口独立复核：

```powershell
python official/multicore_cut_evaluate_problem_2.py data/case_019.json results/plans/case_019_p2_n5.json --config data/config.txt -o outputs/check.json --trace-output outputs/check_trace.json --log-output outputs/check_log.txt
```

官方命令同时输出结果JSON、Perfetto Trace及文本日志。Trace可通过Perfetto工具查看。

## 4 从头复现全部100个用例

提供两条求解路径，均保持原始官方评估程序不变，并保存对应场景的真实官方最终结果。为保留交付结果，两条路径分别使用新的输出目录。

**官方逐候选评分路径**：问题一候选直接由官方场景 A 评分，整图候选可复用官方单核基准。

```powershell
python src/run_experiments.py --mode full --workers 6 --output results_reproduced --budget standard
```

**等价证书评分路径**：对满足“每核至多一个 Task、无 Task 间通信”的候选，比较官方 A/B 构造出的逐 Pipe 操作、工作量、DDR 标记与有效依赖偏序。只有逐实例证书通过时才用官方 B 的结果作为问题一候选评分；证书失败就回退完整官方 A。若证书评分的候选最终胜出，必须重新运行官方 A，并确认 Makespan 与完整搬运字典相同后才保存正式结果。这只减少可证明等价候选的搜索开销，不改变候选集或正式评分口径，也不假设场景 A/B 普遍等价。

```powershell
python src/run_certified.py --workers 6 --output results_certified --budget standard
```

证书路径会自行补齐缺少的单核基准，支持 `--cases`、`--cores` 选择范围；它没有 `--mode` 或 `--wait-baselines` 参数。证书及来源分别保存在 `certificates/`、`candidates/` 和 `certified_engine_manifest.json`。两种调度程序不要同时向同一输出目录写入结果。

首次完整运行会先计算所有单核基准，再进行三种场景评估。最大用例的官方模拟明显较慢，完整复现应预留充足时间。可先用小用例检查环境：

```powershell
python src/run_experiments.py --mode full --workers 2 --cases case_019 --cores 1 5 --output results_demo
```

同一输出目录允许在相同源代码、数据、配置与预算下续跑；检测到不一致时程序拒绝混用旧结果，应改用新的输出目录。不要删除版本检查来复用不同实验的结果。

如需并行准备基准和调度，在两个终端分别运行下列命令，保持相同输出目录与用例范围；一般使用者直接运行前述单条完整命令即可。

```powershell
# 终端一
python src/run_experiments.py --mode baseline --workers 4 --output results_reproduced
# 终端二
python src/run_experiments.py --mode full --wait-baselines --workers 6 --output results_reproduced --budget standard
```

`--wait-baselines` 需要基准进程正在运行，或所选用例的全部基准已经存在；否则会等待尚未产生的基准文件。

## 5 校验与可视化

```powershell
python src/validate.py --results results
python src/analyze_data.py
python src/plot_results.py --trace results/official_results/case_019_p2_n5.json.gz
python src/build_paper.py --output A题_多核调度完整论文.docx
```

校验器检查方案覆盖、依赖、流水线区间、同步延迟、容量峰值、数据搬运恒等式、Cache字节命中率及完整性。绘图脚本从实算结果读取数值，不内置论文成绩。论文生成脚本要求100个用例、5种核数、3种场景完整覆盖；内部排版预览选项不应用于最终交付。

上述命令默认处理随包交付的 `results`。如果需要检查刚生成的 `results_reproduced`，应显式指定对应目录：

```powershell
python src/validate.py --results results_reproduced
python src/analyze_data.py --output-dir results_reproduced
python src/plot_results.py --results results_reproduced/results.csv --features results_reproduced/dataset_features.csv --candidates results_reproduced/candidates.csv --cache-pairs results_reproduced/cache_pairs.csv --trace results_reproduced/official_results/case_019_p2_n5.json.gz --output-dir figures_reproduced
python src/build_paper.py --results results_reproduced/results.csv --figures figures_reproduced --output A题_多核调度复现论文.docx --manuscript paper_reproduced.md
```

`cache_pairs.csv` 不存在时，绘图脚本会从指定的 `results.csv` 中读取问题三的同方案 Cache 对照。

以上 Word 命令显式将论文写入当前项目目录。`--results` 接收 CSV 文件路径，`--figures` 接收图片目录；对应结果目录中还须有结构特征、候选记录、原始时间线和通过校验的报告。附录 A 将 1500 条场景结果按“用例、核数”合并为 500 行，每行并列给出 A、B、C 三种场景的周期与额外搬运量。

完整结果集与源文件的一致性由 `results/run_manifest.json` 及原始输入哈希清单记录；证书路径另保存 `certified_engine_manifest.json`。修改算法后，请重新生成结果并同步更新论文。对 `results_certified` 的校验、绘图和生成 Word 方法相同，将上述命令中的结果路径相应替换即可。

交付前已纠正一个仅涉及展示的任务计数字段：官方 A 没有 `task_count` 字段，原包装层的默认值 1 不能代表多 Task 方案；官方 B/C 的该字段还包含空闲核心上下文。当前分别保存原值 `official_task_count`（A 为空）与按方案推导的 `executed_task_count_derived`（A 为子图数，B/C 为非空核心数）。`results/metadata_corrections.json` 记录更正前后包装层哈希，`results/source_revisions.json` 解释源码展示字段修订，`results/provenance/metadata_revision` 保留实际计算时源码、清单及旧包装层记录。全部 1600 个原始官方结果和单核基准文件保持逐字节不变，方案、选优、周期、搬运、Cache 与耗时指标均未改动。

## 6 统计口径

- 问题一、二：先对每个用例计算“官方整图单核Makespan/多核Makespan”，再对100个比值取算术平均。单核加速比按题意为1。
- 问题三：使用第二问同一份方案分别评估无L2与只读L2，平均值为逐例时间比的算术平均。
- `added_copy_bytes` 是官方逻辑额外搬运量。L2命中不会直接从该字段扣除。
- `physical_ddr_bytes_derived` 等于官方调度后COPY字节减去Cache命中字节。在本题数据与官方构图规则下，它表示评估模型中实际由DDR服务的数据字节数，属于派生指标；不是硬件实测的总线传输量。
- Cache命中率按字节统计，不是命中次数除以总访问次数。
- 最终方案是已评估候选中的最好可行解，不提供组合优化问题的全局最优保证。

## 7 代码模块

`solver.py` 负责图投影、分量聚合、链收缩、拓扑深度窗口、负载分配及通信感知列表调度；`evaluate.py` 是对原始评估器的轻量封装；`run_experiments.py` 负责候选选优、并行运行、缓存与结果记录；`validate.py` 独立检查结果；`analyze_data.py`、`plot_results.py` 和 `build_paper.py` 分别负责数据审计、制图与论文生成。

`certified_evaluate.py` 检查逐实例有效偏序等价证书；`run_certified.py` 使用证书评分并对胜出的代理方案进行官方场景 A 复评。原始 `run_experiments.py` 保留为直接官方评分的复现路径。

所有正式结果使用附件固定的L1、UB、DDR、跨核等待和L2参数，不修改官方评估程序。算法参数、有限搜索预算以及未针对L2单独优化等边界均在论文中说明。
