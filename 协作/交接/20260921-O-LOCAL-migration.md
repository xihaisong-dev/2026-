# 新版工作流迁移交接

- 任务：LOCAL-20260921-O-02，用户要求统一到最新完整技能
- 提交人：Codex；接收人：O（角色占位，账号待填）
- 时间：2026-09-21（北京时间）
- 交接状态：READY，尚未代填人工接收
- 分支：main；此次初始化维护按用户迁移要求直接集成
- 产物 SHA：2d667671fb95ec2728ebef3dbf1c8acb30689afe
- 输入版本：586e3bb3b908f94c53dcd9d4f4b77a198c1f2cb5
- 技能输入：协作/技能版本锁.json，完整源提交和逐文件 SHA-256 已登记

## 已完成

移除旧编号目录和 workflow_guard，迁移四角色、任务、PR 和双向交接模板。固定完整 meta-model-agent 脚本与协议，新版中文目录和 gmcm 状态由初始化器创建。唯一状态为状态/工作流状态.json，当前 DISCOVERY / ready，未开始研究。

## 接手命令

在独立 clone 的仓库根目录，Python 3.10+：

```bash
python mm.py stage current
python mm.py pipeline overview
python 协作/工具/check_repository.py
python 协作/工具/verify_migration.py
```

实际结果：仓库与技能哈希检查退出码 0；GMCM 默认初始化、前置缺输入阻断、失败不改状态、重复初始化不覆盖状态均通过；Git 暂存树导出的独立目录也可运行，无须个人技能安装。验证摘要在协作/迁移验证.json。未运行比赛门禁/模型/论文编译，run-id 不适用；远端 Actions 状态未核验。

## 接口变化与限制

D-002（协作/迁移说明.md）替代旧目录约定；无既有研究结果需要重跑。此前旧初始化交接仅保留历史。字体二进制未分发，正式编译时准备所需字体。不能把技能自带模板或历史规则当成当届已核验材料。

下一步：O 让四位角色在各自 clone 执行上述命令；待题面和官方模板到位、AI 使用报告开关明确后，再通过 mm.py intake 导入并 begin DISCOVERY。不得重新创建旧工作流。

## 接收确认

接收人、接收时间、检出版本、复核证据和 ACCEPTED / CHANGES_REQUESTED 结论待 O 填写并提交。
