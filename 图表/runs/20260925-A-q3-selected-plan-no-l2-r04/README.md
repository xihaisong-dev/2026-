# 问题三最终方案的无 L2 官方重放

本目录只补足问题三最终方案 `p^C` 在场景 B（无 L2）下的 500 组评价，不改变原 Q2-r07 和 Q3-r03 的优化结果。`pairs.csv` 按 100 图 × 1—5 核列出四个配对周期：问题二方案无 L2、问题二方案开 L2、问题三最终方案无 L2、问题三最终方案开 L2。每组的 `official_no_l2.json.gz` 是题目原始场景 B 评价器的完整返回；`metrics.json` 记录输入与最终方案 SHA-256。`verification.json` 记录 500 组复核结果。

在仓库根目录执行：

```powershell
python 程序/q3_no_l2_replay.py --output 图表/runs/新运行目录 --workers 6
python 程序/q3_no_l2_replay.py --output 图表/runs/新运行目录 --verify-existing
```

运行前先依 `程序/q1_io.py` 从原始附件导入 `数据/processed/q1/` 并完成哈希验证。脚本读取冻结的 `图表/runs/20260924-A-q3-full-r02/` 500 份最终方案及 `图表/runs/20260924-A-q3-delivery-r03/pairs.csv`，不重新搜索。五核同方案逐图时间比定义为 $100^{-1}\sum_i T^B_i(p^C_i)/T^{L2}_i(p^C_i)=1.024077$；跨方案综合比为 $100^{-1}\sum_i T^B_i(p^B_i)/T^{L2}_i(p^C_i)=1.022567$。两个比值的方案口径不同，均非总周期比。
