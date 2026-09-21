# 2026 华为杯 XeLaTeX 模板

本目录是依据 2026 年官方 DOC 与格式规范制作的 LaTeX 适配版，不是组委会发布的原生 LaTeX 模板。官方封面和摘要抬头以矢量 PDF 保留；原始文件与来源哈希见仓库 `协作/赛前研读/官方2026/`，衍生资产说明见 `assets/来源.json`。

## 编译

在仓库根目录运行：

```powershell
python 协作/工具/compile_template.py
python 协作/工具/compile_template.py --source main
```

第一条生成 `output/pdf/2026模板试编译.pdf`，明确标为排版示例；第二条生成含待填内容的空白骨架，均不能当作正式论文提交。脚本执行三遍 XeLaTeX，保留日志，发现缺字、未解析引用或越界时停止。

依赖：XeLaTeX、CTeX、amscls、amsmath、amsfonts、geometry、fontspec、pdfpages、pgf、booktabs、caption、listings、appendix、cleveref 等。当前使用 Windows 的宋体、黑体、楷体、Times New Roman、Arial 和 Consolas；字体不随仓库分发。在其他系统上需先提供合法可用字体并调整字体配置，再重新检查 PDF。

## 填写

1. 编辑 `main.tex` 的 `PaperTitle`、`PaperKeywords` 和封面五个字段。字段默认留空，官方三名队员栏保持不变。协作的四个角色不是四名正式参赛队员。
2. 填写 `sections/0_abstract.tex` 及实际子问题章节。默认三个子问题仅为骨架，按题目问数增删，不强制每问新建模型或目标函数。
3. `sections/references.tex` 中启用真实参考文献环境，删去其独立占位标题，按正文首次引用顺序写 `bibitem`，用 `cite` 引用。
4. 正式源文件是 `main.tex`。编译脚本从此文件生成临时 `preview.tex`，只在试编译时替换封面字段、摘要、正文和程序示例。`main.tex` 不引用 `demo/`，演示内容不会混入正式源码分析。
5. 正式写作时由 W 将 `main.tex`、`gmcmthesis.cls`、`assets/` 和 `sections/` 复制到 `论文/`，主文件改名为 `论文正文.tex`；勿覆盖现有论文，不复制 `demo/`（源码检查会扫描论文目录内所有 tex）。随后按正式工作流核验并生成最终 PDF。

## 格式与边界

- 标题三号黑体，一级标题四号黑体居中，其他中文小四宋体，正文单倍行距；英文与数学按相应字体排版。
- 封面无页码；摘要从 1 开始，页脚居中连续编号，无页眉；摘要一般不超过两页，之后另页开始正文。
- 默认不生成目录。若后续明确需要，可将 `\gmcmtocfalse` 改为 `\gmcmtoctrue`，最多展示三级；2026 已核验格式规范未要求单独目录。
- 页边距参照官方 Word 样式，采用上 30、下 18、左右 22.5 mm；这是本适配实现，不冒称官方明文毫米值。官方材料未列出正文 30 页硬上限或下限。
- AI 附录由工作流声明管理；试编译不替团队声明是否使用 AI。正式报告中的责任声明和使用情况必须由实际参赛者核实，未发生的工作不得照抄成已完成。
- 本次验证针对 XeLaTeX/PDF 路线；DOCX 导出器不在本次格式适配验证范围内。

每问内容与数字复核使用仓库 `协作/写作核对/` 的两个空白表。`模板/` 是工作流同步目录，在其中作出的研究内容修改可能被阶段工具重置；正式稿应放 `论文/`。
