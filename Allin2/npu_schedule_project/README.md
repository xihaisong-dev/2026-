# Allin2 NPU 多核调度

Allin2 是面向问题一多核 NPU 调度的结构化候选生成与官方评估驱动求解器。项目将计算图建模为带依赖、Pipe 周期和张量字节量的 DAG，生成窗口切分、通信感知切分、连通分量合并、Pipe 负载平衡、容量感知批处理和校准 HEFT 等候选，再使用官方评估器按完工时间和额外搬运量选优。

## 项目结构

- `data/`：100 个计算图和评估配置。
- `src/`：候选生成、局部搜索、评估封装和批处理入口。
- `official/`：问题一至问题三官方评估代码及算法说明。
- `official_checksums.json`：官方代码和输入数据校验摘要。

## 环境

推荐使用 conda：

```powershell
conda env create -f environment.yml
conda activate npu-scheduling
```

也可以在已有 Python 3.12 环境中安装：

```powershell
python -m pip install -r requirements.txt
```

问题一、官方评估器和核心调度代码主要使用 Python 标准库；完整环境文件保留了结果分析所需的依赖。

## 运行

在项目根目录运行一个问题一、5 核 case：

```powershell
python -u src/run_experiments.py --mode full --problems 1 --cases case_067 --cores 5 --workers 1 --budget standard --output results_case_067
```

运行全部 100 个 case 的问题一、5 核：

```powershell
python -u src/run_experiments.py --mode full --problems 1 --cores 5 --workers 1 --budget standard --output results_p1_n5
```

`--workers` 控制同时运行的 case 数；`--eval-workers` 控制单个 case 内官方候选评估的进程数。增加并发可降低部分机器上的墙钟时间，但会增加资源占用。不同设备和并发设置下的搜索时间不能直接比较。

## 评估口径

单题加速比为 `T1 / T5`，100 个 case 的平均值是逐题加速比的算术平均。候选按以下三元组选择：

```text
(makespan, added_copy_bytes, method_name)
```

正式问题一、5 核汇总位于项目上一级的 `summary_p1_n5_delivered.json`。该交付结果的平均加速比为 `4.026823910`，相对 Allin 基线提升 `0.132480202`，38 个 case 提升、62 个持平、0 个回退。

600 秒是效率目标，不是本项目自行设定的合法性判定。远程高并发可能显著降低搜索墙钟；低并发环境下部分大图仍可能超过该时间。报告结果时应同时注明设备、评估并发和时间字段定义。

## 版本说明

`summary_p1_n5_delivered.json` 来自正式交付运行，运行目录中的清单记录了当时的源码哈希。之后 `src/run_experiments.py` 增加过只修正搜索计时起点的补丁，用于避免共享单核基准时间混入首个搜索窗口。该补丁不改变候选生成、官方评估、方法选择或加速比，但会使当前源码哈希与旧运行清单不同。若需要严格逐字节复现正式汇总，应使用结果运行清单对应的源码版本；若使用当前源码重跑，应把它视为新的复核运行。

## 许可证与数据

本仓库上传前应补充与参赛代码和数据授权相符的 `LICENSE` 文件。若数据或官方评估代码不允许公开，应仅公开求解器源码和脱敏示例，并将完整数据和评估结果作为受限附件保存。
