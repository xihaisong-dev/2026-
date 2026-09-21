# 四人协作指南

## 第一次加入

仓库所有者邀请成员后，各自在自己的电脑和目录克隆：

```bash
git clone https://github.com/xihaisong-dev/2026-.git
cd 2026-
git config user.name "你的名字"
git config user.email "你的 GitHub 提交邮箱"
```

先填写 `00_admin/TEAM.md`，再领取 Issue。目录负责人负责接口与审阅，其他人可以协助；修改别人的主责目录前，先在任务里明确范围和接收人。

## 开始一项任务

确认 `git status` 干净，未完成工作先提交到自己的分支，然后执行：

```bash
git switch main
git pull --ff-only origin main
git switch -c model/12-baseline
```

分支格式为 `admin|model|code|paper|review/<Issue编号>-<英文短名>`。上例中的 12 替换成实际 Issue 编号。每个任务有唯一负责人、交付物路径、验收条件、接收人和截止时间，时间使用北京时间 `YYYY-MM-DD HH:mm +08:00`。

## 提交与同步

```bash
git status
git diff
git add 03_model/ANALYSIS_MODELING_REPORT.md
git commit -m "model: 完成基线模型定义 (#12)"
git push -u origin model/12-baseline
```

只暂存当前任务相关文件，不提交密钥、环境目录或临时大文件。第一次 push 后到 GitHub 创建 PR，使用仓库自带模板。

需要同步 main 时，在自己的任务分支执行：

```bash
git fetch origin
git merge origin/main
```

冲突由任务负责人和相应目录负责人核对解决；不要用整文件覆盖或强推掩盖冲突。共享分支不 rebase、不 force-push。合并后重新验证受影响的命令和结果。

## 交接与合并

1. 提交实际产物，记录该次提交 SHA；交接单引用这个 SHA，避免引用包含交接单自身的循环版本。
2. 复制 `00_admin/handoffs/TEMPLATE.md`，命名为 `日期-角色-Issue编号-短名.md`，填写输入、命令、产物、限制和下一步。没有运行就写 `NOT_RUN`。
3. 单独提交交接单并 push；PR 关联任务和交接单，将交接状态置为 `READY`。
4. 接收人在独立 clone 中检出交付版本，按交接单验证；补写验收时间、结论和证据，状态改为 `ACCEPTED` 或 `CHANGES_REQUESTED`。接收记录也必须提交。
5. 至少一名非作者审阅后，由 O 统筹检查并合并 PR。任务验收完成、交接已接收且 PR 已合并后才关闭 Issue。

若 O 是作者，由对应接收人审阅，再由 O 合并。阻塞时把 Issue 标为 `BLOCKED` 并记录原因、需要谁处理及临时可推进的工作。

## 换班或离线前

推送当前分支，即使未完成也可以开 Draft PR；填写交接单，列出最后可用版本、未提交的大文件位置、失败命令、下一条具体操作。`DRAFT` 不代表可直接用于下游正式产出。

## 文件和结果约定

- 原始题面和数据置于 `01_problem/original/`，登记来源与 SHA-256；不得清洗覆盖原文件。
- 处理数据放 `04_code/data/processed/`，可再生成的大文件默认不跟踪；需交接的外部文件记录稳定下载位置、权限、大小和哈希，禁止只填本机绝对路径。
- 一次实验一个新目录，如 `05_results/runs/20260921-210000-E-q1-baseline/`；不同成员用角色和时间区分，不覆盖旧运行。
- 主指标、输入输出接口和单位在运行前约定；改变后写 `00_admin/DECISIONS.md`，说明哪些结果和论文段落需要重做。
- 论文中的数值引用正式指标和 run-id，图表源数据存 `05_results/figure_data/`；最终图复制到 `06_paper/figures/` 并登记来源。
- 多人协助论文时拆分 `06_paper/sections/`，由 W 统一修改入口、参考文献和版式。

## 阶段核验

共享工具只需 Python 3.10+ 标准库，不依赖本机 Codex 安装：

```bash
python -X utf8 tools/workflow_guard.py status --workspace .
python -X utf8 tools/tool_locator.py xelatex drawio pdftoppm
```

初始化时门禁显示 FAIL 是缺少正式资料的预期结果。门禁 PASS 和任务完成是不同含义。详细阶段推进方式见 `00_admin/WORKFLOW.md`。
