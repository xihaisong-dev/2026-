# GMCM 条件式 AI 使用说明

## 适用边界

本规则只处理 NPGMCM/GMCM 当届材料中的 AI 使用披露要求。赛题、官方论文模板和组委会通知的原文优先；参考报告只能提供填写结构，不能替代官方规则，也不能据此推断所有届次都强制提交 AI 报告。

## 判定流程

每次上传 GMCM 赛题时必须同时手动声明是否启用报告。初始化时直接上传赛题的示例：

```bash
python scripts/workspace_init.py --workspace . --competition gmcm --problem ./题目.pdf --template ./论文模板.doc --ai-disclosure required
```

已有工作区再次导入赛题时同样必须带 `--ai-disclosure required|off`。缺少声明时导入命令必须停止并提醒用户；仅初始化但尚未上传赛题的空工作区可暂时保持 `pending`。上传后若需更改，运行 `scripts/ai_disclosure.py --mode required|off --evidence <依据>`。若材料相互冲突或含义不明，先向用户确认，不得自行选择 `off`。

## 报告结构

当模式为 `required` 时，使用 `sections/B_ai_disclosure.tex`，并置于论文附录。报告至少包含：

- 责任声明；
- AI 工具名称、提供方、型号或版本和使用日期；
- 实际使用环节、具体用途与影响范围；
- 关键交互摘要；
- 是否采纳、人工修改、独立核验和采纳理由；
- 团队独立完成内容与真实性确认。

同时建立 `论文/AI使用记录.json`。每条记录至少包含 `tool`、`provider`、`model_version`、`date`（`YYYY-MM-DD`）、`stage`、`purpose`、`interaction_summary`、`adoption`、`human_revision`、`verification` 和 `evidence_refs`。`evidence_refs` 至少引用一个位于当前工作区内且实际存在的文件，例如脱敏后的交互摘要、人工复核记录或版本化修改记录。推荐结构：

```json
{
  "responsibility_confirmed": true,
  "truthfulness_confirmed": true,
  "records": [
    {
      "tool": "实际工具名称",
      "provider": "提供方",
      "model_version": "实际型号或版本",
      "date": "2026-08-29",
      "stage": "实际使用环节",
      "purpose": "具体辅助用途",
      "interaction_summary": "关键提问或任务摘要",
      "adoption": "accepted/partial/rejected 或 采纳/部分采纳/未采纳",
      "human_revision": "团队作出的修改",
      "verification": "独立核验方法与依据",
      "evidence_refs": ["日志/AI使用证据/record-1.txt"]
    }
  ]
}
```

机器门禁会拒绝未填写占位符、空字段、无本地证据的记录，以及未在附录中反映工具、版本、环节或关键交互的记录。结构化文件和本地证据提高可审计性，但仍可能被人为虚构，因此门禁只能验证完整性和相互一致性，不能替代团队的真实性确认或竞赛方审查。

推荐责任声明为：

> AI 仅作为辅助手段，模型假设、核心推导、创新点、结果分析由参赛团队独立完成。

允许在不改变含义的前提下调整文字，但必须同时表达 AI 仅作辅助、上述核心研究工作由团队独立完成。不得只保留模板责任句而不填写实际使用记录，也不得虚构未使用、未采纳或独立完成情况；如果实际过程与该声明不一致，应如实披露并按当届规则处理。

## 匿名与内容边界

报告位于封面之外，不写学校名称、队伍编号、队员姓名、联系方式或其他身份信息。只概述与论文有关的关键交互，不粘贴无关长对话、隐私数据、账号信息或无法核验的输出。示例报告中的具体题目、队伍、日期、工具版本和交互内容不得复制到新论文。
