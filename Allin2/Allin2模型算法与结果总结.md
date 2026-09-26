# Allin2 模型、算法与结果总结

## 1. 项目概况

Allin2 是在 Allin 求解器基础上融合多轮候选生成与精修方法的独立版本，目标是降低问题一、5 核的官方 Makespan。评估仍使用 Scene A 官方评估器，算法生成多个合法 plan 后由官方指标选优。

- 项目代码：`Z:\YuyanData2\codex\数学建模2026\9.25优化v2\Allin2\npu_schedule_project`
- 100-case 汇总：`Z:\YuyanData2\codex\数学建模2026\9.25优化v2\Allin2\summary_p1_n5.json`
- 超时记录：`Z:\YuyanData2\codex\数学建模2026\9.25优化v2\Allin2\timeouts_p1_n5.csv`
- 远程测试主机记录：`jishishan-remote`，Conda 环境 `yolonew`

官方问题一评估器哈希与 Allin 原项目一致：`2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`。因此以下比较使用同一评估器实现。

## 2. 100-case 结果

将 Allin2 汇总中的 100 个 case 与 Allin `npu_schedule_project\results_p1_n5\results.csv` 按 case 对齐后，得到：

| 指标 | Allin 基线 | Allin2 | 变化 |
|---|---:|---:|---:|
| 问题一、5 核平均加速比 | 3.894343708 | **4.014266185** | **+0.119922477** |
| 100-case 加速比增量总和 | - | **+11.992247743** | - |
| 严格提升 case | - | **37** | - |
| 持平 case | - | **63** | - |
| 回退 case | - | **0** | - |
| 无效候选 | - | **0** | - |

平均加速比按 100 个逐案 speedup 的算术平均计算。加速比范围为 `1.249723` 至 `5.501141`。因此 Allin2 的汇总结果超过 3.9 目标；这是目录中 `summary_p1_n5.json` 的 100-case 结果，不是从少数典型 case 外推出来的。

### 增量最大的 case

| 排名 | Case | 方法 | Allin speedup | Allin2 speedup | 绝对增量 |
|---:|---|---|---:|---:|---:|
| 1 | case_056 | `vw24_10_t15_peftins` | 1.865367 | 3.311657 | **+1.446289** |
| 2 | case_075 | `vw24_10_t15_heft2` | 2.217830 | 3.659507 | **+1.441677** |
| 3 | case_009 | `vw24_8_t25_peftins` | 2.060458 | 3.006356 | **+0.945897** |
| 4 | case_082 | `vw24_10_t15_peftins` | 2.389341 | 3.158609 | **+0.769268** |
| 5 | case_035 | `vw32_8_t15_peftins` | 2.371921 | 3.046003 | **+0.674082** |
| 6 | case_050 | `cav16_8_t15_b65536_peftins` | 2.186500 | 2.841873 | **+0.655373** |
| 7 | case_068 | `vw24_8_t25_peftins` | 2.037114 | 2.567285 | **+0.530171** |
| 8 | case_043 | `vws18_54_t78_x` | 3.215526 | 3.678056 | **+0.462530** |
| 9 | case_005 | `vw24_10_t15_peftins` | 1.636538 | 2.070729 | **+0.434191** |
| 10 | case_086 | `ls_vws8_24_t48_x` | 1.648585 | 2.080531 | **+0.431946** |
| 11 | case_039 | `component_group7` | 4.103011 | 4.534191 | **+0.431180** |
| 12 | case_049 | `vws9_18_t32_x` | 2.290402 | 2.708114 | **+0.417712** |

提升主要集中在原始加速比较低、且主导连通分量明显或层宽变化大的图。Allin2 保留旧候选，因此新增算法未胜出时通常由原方案持平兜底。

## 3. 建模算法

Allin2 不是单一调度算法，而是一个**结构候选生成 + 官方模拟筛选 + 受预算控制的局部精修**框架。入口在 `src/solver.py::generate_candidates`，最终选优与精修在 `src/run_experiments.py`。

### 3.1 基础图建模与任务分组

把计算图建模为 DAG。节点代表算子，边代表数据依赖并携带 tensor 字节数；每个算子带有 Pipe 类型与周期。候选方法将节点分组成子图 Task，再决定 Task 的核归属和每核执行序列。官方评估器负责检查合法性并计算真实 Makespan、跨核等待、数据搬运和容量溢出等指标。

基础 HEFT 代理时长大致采用：

```text
duration = max(pipe_cycles) + 0.08 * sum(pipe_cycles)
```

HEFT/PEFT 风格的向上秩和通信代价用于生成与排序候选，不代替官方最终评分。

### 3.2 分层与变宽深度窗口

`stitch_candidates.py`、`extra_candidates.py` 和 `extra_candidates_ext.py` 生成多种图结构候选：

- 固定深度窗口、按关键工作量加权的窗口以及通信感知切分。
- `vw*` 固定网格变宽窗口：DAG 窄脊区域采用较宽窗口，减少切断关键链；宽扇区域采用较窄窗口，保留可并行任务。
- `vws*` 搜索式变宽窗口：根据各深度层的节点数分布推导窄/宽窗口参数，而不是仅依赖人工固定配置。
- `hyb*` 混合链/宽带分区：链式区域粗分，宽层区域细分。
- `segs*` 按边字节量设置流水段切点，尽量选择通信较轻的边界。
- `critical_cut*` 在工作量均衡范围内寻找跨切边字节较低的切点。

这些策略都按图的结构触发，不使用 case 编号或已知成绩作为策略条件。

### 3.3 多分量、Pipe 负载和容量感知候选

- 弱连通分量可按组大小打包，再以 LPT 或 Pipe 负载向量分配到各核，减少核间工作量失衡。
- `pipevec_merge`/`kios_pipe_vector_lpt` 利用多 Pipe 负载向量分配组件，而不是只看总算子周期。
- `membatch*` 根据组件触及的 L1/UB tensor 容量做分批，控制单个 Task 的工作集，缓和容量和 spill 搬运压力。
- `cav*` 在变宽窗方案中加入出边字节阈值，限制高通信切分。
- `pipe_seg*` 与按字节分段候选探索不同的拓扑流水粒度。

### 3.4 校准时长 HEFT 与固定分区重平衡

`src/calibrated_heft.py` 针对固定 `0.08` 重叠系数可能低估真实 Task 时长的问题，引入 Pipe 时长混合模型：

```text
duration(w) = w * max_pipe + (1 - w) * sum_pipe
```

对多个 `w` 与窗口宽度生成候选，使核分配能适应不同图中的 Pipe 重叠程度。`rebal*` 则保留既有分区不变，只按校准后的 Task 时长重新安排核归属和核内顺序，以较小改动改善负载均衡。所有候选仍由官方评估器裁决。

### 3.5 plan 级局部搜索

`src/ls_p1n5.py` 在已有最优 plan 上保持 `node_to_subgraph` 分区不变，只搜索子图到核的迁移和跨核交换。每次重建每核队列时按子图依赖图的固定拓扑秩排序，保证顺序合法。官方评估器以 `(makespan, added_copy_bytes)` 比较邻域方案；只有严格优于种子才接受，因此局部搜索本身不会把种子结果变差。

搜索预算按图规模分档：最多迭代次数、参与移动的重子图数量和官方评估次数随图规模增大而下降；`nops > 9000` 跳过此局部搜索。`run_experiments.py` 还要求构造式候选的官方评分累计时间低于 600 秒才启动局部搜索，因此超慢 case 会跳过额外精修。

### 3.6 候选筛选与零回退设计

Allin2 将新增候选追加在已有 keeper 之后，并用方案指纹去重。runner 对候选调用官方评估器，按 Makespan、搬运量和方法名的稳定顺序选优；单核整图基准按项目规则处理。设计意图是保留已有基线方案作为安全下界，新增候选不佳时回退到已有方案。100-case 对比中观察到 37 胜、63 平、0 负，与该设计意图一致。

## 4. 运行时间与测试状态

100-case 汇总的平均 `search_evaluation_seconds` 约 `708.98s`，最大 `3371.61s`，平均候选数约 `46.55`，最大候选数 `86`。`timeouts_p1_n5.csv` 有 51 条记录事件、涉及 49 个不同 case，记录状态为 `completed_after_target`，表示结果最终完成但超过 600 秒软目标；最长为 `case_087` 的约 `3371.61s`。因此算法成绩完成度高，但完整搜索成本较高，600 秒不能视为所有 case 均满足。

在已优化的 100-case 结果中，以下两个 case 的官方候选搜索时间低于 600 秒：

| case | 优化方法 | 搜索时间 |
|---|---|---:|
| case_014 | `rebal0_component_batches` | **417.54s** |
| case_091 | `component_batches` | **407.84s** |

对照而言，`case_072` 为 `634.00s`，`case_076` 为 `619.13s`，均超过 600 秒，因此不列入“低于 600 秒”的 case。

## 5. 结果文件与复核边界

- `summary_p1_n5.json`：100 个 case 的最终方法、speedup、Makespan、候选数、无效候选数与评估耗时。
- `timeouts_p1_n5.csv`：超过 600 秒的运行记录，含远程命令和输出目录。
- `npu_schedule_project/src/solver.py`：多族候选的主入口与候选保留/去重。
- `npu_schedule_project/src/stitch_candidates.py`：分层、通信感知、分量与容量候选。
- `npu_schedule_project/src/extra_candidates_ext.py`：搜索式变宽窗、按字节流水段、混合窗与跨核感知放置。
- `npu_schedule_project/src/calibrated_heft.py`、`allin2_layer.py`：时长校准和固定分区重平衡。
- `npu_schedule_project/src/ls_p1n5.py`：官方评估器引导的 plan 局部搜索。
- `npu_schedule_project/src/run_experiments.py`：候选评估、官方复核、精修和结果写出。

复核最终成绩时应以固定 Allin 基线 CSV、Allin2 对应的完整运行产物及未修改官方评估器重新对齐为准。
