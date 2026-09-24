# 全局成本机制校准与预算机会审计

本报告旧基线指冻结的component_local_rank全量实验，不表示main默认已更新。固定三轮Pipe/依赖/DDR代理；不拟合逐例系数、不改变候选池和候选排序。准入只比较同口径候选与当前解。代理不是完整官方全局仿真；核内准备和代理耗时另列。

扩展条件通过：True。

## development

同预算相对未筛选：1胜/31平/0负，合计时间下降0.010062%，额外搬运下降0.000000%。
固定当前解与同候选池预测诊断：{'n': 30, 'preparation_seconds': 934.9222553875297, 'local_preparation_calls': 60, 'local': {'correct_decisions': 24, 'false_rejects': 2, 'false_accepts': 4, 'candidate_mape_pct': 11.288912983746775, 'incumbent_mape_pct': 7.5273084623527575}, 'event': {'correct_decisions': 30, 'false_rejects': 0, 'false_accepts': 0, 'candidate_mape_pct': 1.6612025737595661, 'incumbent_mape_pct': 1.2869059473846645}}。

|核心|旧基线平均加速比|未筛选|事件筛选|
|---|---:|---:|---:|
|1|1|1|1|
|2|1.813053|1.970864|1.970864|
|3|2.274845|2.699788|2.699788|
|4|2.723035|3.263434|3.264292|
|5|3.050559|3.620528|3.620528|

退步配置（完整保留）：
- 无。
## extension

同预算相对未筛选：0胜/64平/0负，合计时间下降0.000000%，额外搬运下降0.000000%。
固定当前解与同候选池预测诊断：{'n': 48, 'preparation_seconds': 575.454970145598, 'local_preparation_calls': 96, 'local': {'correct_decisions': 38, 'false_rejects': 2, 'false_accepts': 8, 'candidate_mape_pct': 14.96760610787773, 'incumbent_mape_pct': 8.793399178881101}, 'event': {'correct_decisions': 48, 'false_rejects': 0, 'false_accepts': 0, 'candidate_mape_pct': 1.773201106481621, 'incumbent_mape_pct': 2.201061936293989}}。

|核心|旧基线平均加速比|未筛选|事件筛选|
|---|---:|---:|---:|
|1|1|1|1|
|2|1.845829|1.871459|1.871459|
|3|2.291728|2.430394|2.430394|
|4|2.655294|2.880444|2.880444|
|5|2.892110|3.145272|3.145272|

退步配置（完整保留）：
- 无。

## 基础搜索机会成本

{"stage": "development", "case": "case_028", "cores": 4, "new_route": true, "replacement": "structural_memory_lpt", "replaced": "random_migrate", "replacement_at": 5, "already_scored_id": null, "baseline_match_index": null, "baseline_proposal_status": "infeasible", "baseline_rejection_reason": "task schedule: dependency cycle; 168 -[subgraph dependency]-> 169; 169 -[core 2 task order]-> 210; 210 -[subgraph dependency]-> 215; 215 -[subgraph dependency]-> 216; 216 -[core 1 task order]-> 242; 242 -[core 1 task order]-> 168", "direct_gain_in_baseline_prefix": 0, "baseline_missing_improvers": [{"index": 9, "candidate": "local_reschedule", "makespan": 10676362, "prefix_gain": 17880, "plan_sha256": "9cd1467f3f2ff1126f3ce5e67063199a07f3a1258d0428b9ea0eaeeaefbf9070"}], "baseline_final": 10676362, "unguarded_final": 10694242, "guarded_final": 10676362, "causal_scope": "same-plan direct score where matched; missing later improvements are trajectory differences, not isolated causal attribution"}

opportunity_audit.json逐项记录被替代方案的hash匹配及原基线中缺席的有效改进。直接改善按相同方案原基线前缀衡量；后续轨迹差异不能被简单加总为独立因果收益。

预算：{'runs': 192, 'global_search_calls': 2112, 'fixed_reference_hits': 192, 'original_final_replays': 64, 'strict_original_verification_reuse': 128, 'event_extra_local_calls': 156}。
耗时：{'search_seconds_sum_by_variant': {'routes_unguarded': 6219.342858299613, 'routes_event_guarded': 7620.121834980324}, 'max_search_seconds': 445.2067964375019, 'search_over_600': [], 'scope': '16 workers; search excludes fixed-single cold generation and final original replay; comparison records per-run values, not speed guarantee'}。

仅seed0；8图开发与16图扩展分开汇报。只在开发门槛通过时扩展；不据本轮自动替换main、默认或全量100图成绩。候选预测改善不等于最终搜索收益，所有筛选误拒/误放及最终退步必须保留。
