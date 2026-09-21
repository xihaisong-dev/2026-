# 共享工具

Python 3.10+，仅标准库。

- check_repository.py：目录及 JSON 语法检查，对应 GitHub Actions；不检查比赛结论。
- workflow_guard.py：门禁、SHA-256 冻结、冻结验证；不会自动推进 workflow.phase。
- tool_locator.py：发现排版和 PDF 工具，不自动安装。

后两者复制自本机 1start-mathmodel 技能脚本，便于无 Codex 的队友直接执行。上游更新时经 PR 核对再替换。
