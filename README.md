# 2026 华为杯四人协作仓库

本仓库统一使用 **meta-model-agent** 完整版。仓库内固定技能副本位于 `.agents/skills/meta-model-agent/`，版本及哈希见 [技能版本锁](协作/技能版本锁.json)，四个人运行相同版本，不依赖个人 Codex 安装。

当前状态：`gmcm / PDF / baseline / standard`，工作流已初始化，`DISCOVERY` 尚未开始。赛题原件、当届官方论文模板和 AI 报告开关仍待确认；没有通过任何研究阶段或最终验收。

## 开始协作

1. 阅读 [协作指南](CONTRIBUTING.md) 和 [四角色分工](协作/分工.md)。账号继续用 O/M/E/W 占位。
2. 领取 Issue，独立 clone，在任务分支工作。
3. 交班时填写 [交接单](协作/交接/TEMPLATE.md)，接收人按版本和命令验收。
4. 用 `python mm.py stage current` 查看阶段；唯一状态源是 `状态/工作流状态.json`。

## 目录

| 路径 | 内容 | 主责 |
| --- | --- | --- |
| 协作/ | 四人分工、任务、决策、交接、版本锁 | O；各自维护自己的交接 |
| 题目/ | 赛题原件、官方论文模板、导入清单 | M |
| 用户数据/ | 原始附件和用户数据，保持原样 | M/E |
| 数据/processed/ | 经审计、处理并固化哈希的模型输入 | E |
| 问题分析.md、建模报告.md | 正式阶段交付物，阶段执行时创建 | M |
| 程序/、计算结果.md | 可复现求解程序、配置、依赖、计算报告 | E |
| 图表/ | 全部结果.json、图表源数据、运行记录、引用 | E；W 整合 |
| 论文/ | 论文正文.tex、章节、文献、数模论文.pdf | W |
| 状态/、日志/ | 唯一工作流状态和事件记录 | O |
| 当前任务/ | 阶段工具生成的任务包；人工任务仍用 Issue | O |
| 审查/ | 门禁、独立复核、最终验收 | O |
| 工具/、参考资料/、模板/ | 初始化和 begin 按需同步的运行资源 | O |
| .agents/skills/meta-model-agent/ | 固定技能、脚本和源资源，普通任务不修改 | O |

## 七阶段

`DISCOVERY → FORMULATION → COMPUTATION → EVIDENCE → SCHEMATICS → MANUSCRIPT → ASSURANCE`

阶段只通过新版工具推进；不得手改 JSON 把任务标成完成。冠军审稿是可启用的额外质量层，不自动开启。

```bash
python mm.py stage current
python mm.py pipeline overview
python 协作/工具/check_repository.py
```

详细流程见 [工作流说明](协作/工作流.md)、[迁移说明](协作/迁移说明.md)、[GitHub设置](协作/GitHub设置.md)。旧版编号目录和 workflow_guard 已移除，历史仍在 Git 中。
