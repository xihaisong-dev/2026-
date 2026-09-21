# 结果与谱系

一次运行一个新的 runs/<时间-角色-题号-候选>/，不可覆盖。每次保存 run_manifest.json：run_id、status、command、started_at、input_hashes、code_commit、config_path、config_sha256、environment、seed、outputs、error。

metrics.json 与 tournament.json 由 E 汇总正式指标和候选结论；RESULTS_REPORT.md 说明结论及限制；figure_data 保存图表源数据。论文必须可追溯到 run-id。大文件外存时记录可访问位置、权限、大小和 SHA-256；不能只交本机路径。
