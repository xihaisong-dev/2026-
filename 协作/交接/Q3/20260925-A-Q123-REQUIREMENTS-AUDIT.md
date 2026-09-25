# 交接：Q123-REQUIREMENTS-AUDIT — 题面重审及补齐中

## 交付信息

A交后续A，2026-09-25 +08:00，DRAFT（服务器计算进行中）。分支codex/q123-requirements-audit；产物e06abd53，输入8e050d7。无新Issue/PR，未推送。工作树C:/Users/Lenovo/.codex/worktrees/q123-manuscript。

重新读取原始docx正文、数学文字和脚注，来源与哈希在审查/证据/20260925-A-q123-requirements。审核矩阵审查/三问题面复核与补齐_20260925.md为当前事实入口。

## 已修复及验证

定版求解算法未变。新增q23_submit_current.py，显式核验暖初解和核心数，原版完整复核成功后输出case_multicore_res.json，包含入口验证及导出总耗时另记，历史初解生成不计。新增q123_delivery_export.py，已有Q1 500份和Q2/Q3各100份共700份方案按题面命名导出并原版格式检查，通过不等于重新全局模拟；采用先前完整评价证据。

新增q23_delivery_complete.py补齐缺核数和同方案无L2；新增q23_completion_report.py，缺任一配置不生成完整附录。三项实际图单核/配对测试、三项短入口冒烟、缺覆盖保护检查、py_compile通过。程序/code_manifest.json登记源码哈希。旧定版压缩包未覆盖，审核修订另属本提交。

论文摘要和结论仍是旧组合数据，不可当最新稿。论文README已标记历史状态；尚未联动更新正文/图表/附录或重新编译，不宣称可提交。正式门禁NOT_RUN，submit_ready=false，未改状态源或代填人工验收。

## 服务器与接手命令

xihs@120.27.220.233:9022，目录/home/xihs/q1-campaigns/20260925-q23-requirements-completion；Python3.12.14，15并发，PID13296。凭据不写文件。

```sh
cd /home/xihs/q1-campaigns/20260925-q23-requirements-completion
nohup /home/xihs/q1-runtime/run-python -u 程序/q23_delivery_complete.py 图表/runs/20260925-A-q23-requirements-completion > completion.log 2>&1 < /dev/null &
cat 图表/runs/20260925-A-q23-requirements-completion/progress.json
```

启动命令已经执行，不要重复启动！900任务=600低核搜索+200单核验证+100最新Q3五核无L2评价，Q3低核另附同方案无L2。最新观察120/900通过，无失败；后续以服务器实时文件为准。

低核搜索固定590秒、384提议、种子0；外层2400秒只约束异常附录补评/单核核验，不扩大搜索预算。额外无L2评价单列耗时。Q3低核使用r07已验证Q2初解及r02锚点；五核保留既有暖初解来源，须如实披露核数间初始化来源差异，不写统一冷启动。

任务结束生成complete.json、hashes.json及父目录同名-evidence.zip。取回后核验所有哈希，再运行：

```sh
python 程序/q23_completion_report.py 图表/runs/20260925-A-q23-requirements-completion
```

报告入口尚未部署服务器，可本机拉取后运行。它合并已验证的本轮五核Q2和新增低核/单核以及Q3同方案成对记录，所有1000配置完整时输出逐例CSV和五点统计；不使用旧低核成绩兜底。

## 剩余与风险

计算未结束；冷启动初始化总耗时未补证；Q3容量/带宽影响的论文内容仍需按已有敏感性证据核对，不可擅改固定配置作为正式成绩。完成数据后再联动摘要、Q2/Q3章节、曲线、核心代码及附录，并正式编译验收。封面身份/AI声明状态需后续按规范确认，不自动代填。

接收者自行记录完成数和验收结论；不得把DRAFT记为完整提交PASS。
