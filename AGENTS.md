# 本仓库的人机协作约定

- 先读 README、CONTRIBUTING、00_admin/TEAM.md、todo.md 和相关交接单。
- 四个角色代表四位人类协作者；不据此自动启动四个 AI Agent。
- 一个任务一个分支；共享物理目录只能有一个写入者。不得覆盖队友的未提交工作。
- 只改当前任务范围。跨目录或接口变更先记录影响及接收人。
- `01_problem/original/` 保持原样，正式输入必须有来源与 SHA-256。
- 不伪造题面、官方规则、实验结果、运行证据、冻结或验收状态。
- `00_admin/workflow.json` 是阶段状态源；阶段推进由 O 根据真实门禁证据更新。
- 交接使用 `00_admin/handoffs/TEMPLATE.md`，记录产物提交 SHA、实际命令和下一步。
- 不覆盖已有 run-id。未经人工核验的 AI 输出不得标成已验收；记录 AI 用途。
- 后续提交、推送、合并和权限变更遵循用户授权与 CONTRIBUTING.md。
