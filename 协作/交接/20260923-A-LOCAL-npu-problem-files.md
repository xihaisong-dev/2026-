# 交接：LOCAL-npu-problem-files — 赛题原件归档

## 交付信息

- 用户要求：提交题面及附件，并将五篇参考论文复制到桌面文件夹。
- 提交端：A / Codex；接收人：A、B、C 真人操作者。
- 日期：2026-09-23（北京时间）；交接状态：READY。
- 分支：admin/LOCAL-npu-problem-files。
- 产物 SHA：b6ebe651aacd34119802eb638757b2417c054cf6。
- 基线 SHA：0cd8390ba7994438e1643e839ae07549de5c77f6。
- 阶段：仅归档，正式 intake 与阶段门禁 NOT_RUN；工作流状态未改动。

## 产物与来源

- `题目/赛题原件/通用神经网络处理器下的多核调度问题.docx`：297415 bytes。
- `用户数据/通用神经网络处理器下的多核调度问题  附件.zip`：15467848 bytes，117个ZIP条目。
- `题目/赛题文件来源.json`：用户提供的原件路径、SHA-256、大小及完整性检查结果。
- README 与题目 README：更新归档入口及正式导入边界。
- 桌面副本：`C:/Users/Lenovo/Desktop/多核调度参考论文_5篇`，含五篇PDF、阅读索引和文献清单；逐文件SHA-256与文献分支一致。桌面路径不作为团队共享入口，文献共享见PR #2。

## 复现与验证

仓库根目录执行（PowerShell）：

```powershell
$manifest = Get-Content -Raw -Encoding utf8 '题目/赛题文件来源.json' | ConvertFrom-Json
foreach ($item in $manifest.files) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $item.path).Hash.ToLower() -ne $item.sha256) { throw "SHA-256 mismatch" }
}
git diff --check
```

实际检查：原件与副本字节哈希一致；Python zipfile.testzip()检查DOCX容器及附件ZIP均通过；git diff --check通过。未执行附件中的程序。

## 限制与下一步

- 归档不代表官方模板已经正式导入，也不替用户选择AI报告开关。
- 无模型、结果、接口或阶段证据变化。
- 接收人下一步：核对来源哈希，准备官方模板和AI报告选项后通过mm.py intake正式导入。
- 接收人、验收时间、实际验证及接收结论：待接收方填写，提交方不代填。
