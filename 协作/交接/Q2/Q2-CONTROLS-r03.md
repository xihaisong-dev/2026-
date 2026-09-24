# 交接：Q2-CONTROLS-r03 — 初解通信与J预算对照

- 角色：A；接收人：A后续研究；状态：DRAFT，尚非B/C正式派稿证据。
- 日期：2026-09-24 +08:00；分支：codex/q2-placement-j-r03；产物提交：未提交。基础main为50b91d46a7bd43ca404c1285dfc27929496bf266。
- 当前目录：C:/Users/Lenovo/.codex/worktrees/q2-main-r02/2026华为杯数学建模。
- 正式阶段/门禁未推进；已有Q1和r02冻结源码、成绩、索引字段保持。

## 产物和复现

- 报告：审查/问题二初解与J同预算对照_r03.md。
- 完整120份方案、评价gzip、逐候选记录、五点曲线和CSV：图表/runs/20260924-A-q2-controls-r03/。
- 来源与源码：同目录contract.json；审查/证据/20260924-A-q2-controls-r03/source_manifest.json、origins.json、server_receipt.json。
- Python3.12标准库；执行：`python 程序/q2_controls_campaign.py freeze`，`python 程序/q2_controls_campaign.py run --phase development --case 12`，其他图按contract；全齐后`report`，再运行`python 程序/q2_controls_finalize.py`。
- 输出禁止覆盖，复现须独立副本或版本化新OUT；输入需按程序README准备官方processed数据并校验哈希。
- 实际测试命令：`python -m unittest discover -s 程序/tests -p "test_q2*.py" -v`；退出0、13项通过，日志unit_tests.txt。120份最终B回放一致；1248搜索机会、1101实际搜索调用、147缓存命中，最终回放另计。

## 判断与后续

- 新确认018/033/067：通信修正0胜12平0负；混合J0胜11平1负；全引导0胜8平4负。三项均未通过预冻结采用条件，未更改默认、未运行百图。
- 参考HEFT跨轮在048明显改善，但012两核/五核退步；不能按图事后择优声称统一算法改善。下一轮可研究保留有效候选的结构准入，需新冻结协议。
- 确认集偏多分量结构，不能推广到单一大分量图。核内生命周期及重划分本轮未新增。
- 实验只读依赖参考工程；未编辑参考工程或原始输入。没有B/C自动启动或人工验收代填。
- 接收确认：待接收人填写。
