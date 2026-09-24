# 全量冻结说明

最终固定算法开关为 routes_gate_reuse：局部池内排序、三轮事件准入、按结构选择既有memory/hybrid路由、保护四种基础划分以及V2准备复用。事件池内排序在24图对照中未通过，未逐case混入最终算法。每配置seed0、12次评分机会（11次完整全局评分+1次固定单核引用）。

- `full_manifest.json`：400组唯一清单；本机30图、服务器70图；输入、硬件和冻结源码SHA256。全部V2重新运行，不拼入V1记录。
- `selection.json`：预先门槛的判断，回退后已完成的等价验证状态。
- `equivalence.json`：回退版本6组串行配对，以及跨平台探针；缓存不开/开及上一轮的计划、完整结果、候选评分和轨迹一致。一次性小样本计时，不承诺全量加速。
- `transport_provenance.json`：输入包、下载包和清单传输哈希；真实执行命令在各主机execution与summary中。源码修改仅发生在冻结目录之外，运行目录使用固定副本。

开发阶段的服务器调度器在发出开发任务后终止，已经派出的开发worker继续完成；空闲核用于10worker并行扩展。原execution文件未伪造为正常结束，转换原因与PID保存在parallel_transition.json；三个验证批次分别具有completed=true且零失败的summary。全量阶段恢复统一14worker服务器、2worker本机。

复核只复用同输入、同计划字节、完整评价结果相同、且源记录verification_calls=1的证据；不能链式复用。每次搜索全局评分仍实际运行。完整核内准备缓存属于单次求解对象，最多2份划分；分数缓存最多8份完整计划。

分析复现（在仓库根目录，输出目录须不存在）：

```powershell
python 程序/q1_event_full_report.py --run 图表/runs/20260924-A-q1-event-ranking --output 新的验证报告目录
python 程序/q1_event_v2_freeze.py --selection 新的验证报告目录 --output 新的冻结清单目录
python 程序/q1_event_full_report.py --run 图表/runs/20260924-A-q1-event-ranking-v2 --selection 图表/runs/20260924-A-q1-event-ranking-v2-frozen --output 新的全量报告目录
```

运行环境仅Python标准库和不改动的官方评估文件。求解复现使用summary/source_snapshot的源码与manifest固定输入；可省略verified-plan-runs以全部重新做原版最终复核，但大图耗时会显著增加。完整调用参数以各阶段execution文件中的实际命令为准，主机绝对路径按本机目录替换。单核参考来自上一轮经校验的100图固定结果。

额外诊断共155次运行、1705次全局搜索评分；最终400组另计4400次。单测与原版最终复核单独记录。未更新main、正式默认或任何人工门禁。
