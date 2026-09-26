# 六图补充与入文

学习用户提供的中国石油大学（华东）2025A 一等奖论文图形表达，采用白底、少配色、短标签与直接对照。数据和机制均来自本题；未复制参考论文数据。

| 文件前缀 | 内容 | 正文位置 |
| --- | --- | --- |
| fig_scene_paths | 三场景物理数据路径 | 3.10 节 |
| fig_q1_algorithms | 两种算法流程 | 4.5 节之后 |
| fig_q1_complete_curves | 两方法完整 500 配置核数曲线 | 4.12.1 节 |
| fig_q1_case_gains | 五核 100 图成对收益（66胜21平13负） | 4.12.2 节 |
| fig_q2_gantt | 第12图初解与最终方案实际时间线 | 5.7 节 |
| fig_q3_fifo_events | 第39图真实张量 FIFO 事件 | 6.5.1 节 |

每图提供 PDF、300dpi PNG、SVG 和 visual.json；机制图另存 drawio。两个旧 Q1 曲线退出当前正文，历史文件保留。Word 因标题编号规则不同，以对应标题定位。

Q2 在同一官方 B 评价器中复核输入初解与最终方案：13406→11971 周期；逐核计算/搬运区间保留重叠，空白不直接解释为等待。Q3 官方缓存账本通过核对后提取张量 1000000005 的五个事件，节点等距仅表示顺序。源文件哈希见 sources.json。两方法核数曲线来自完整逐例文件；三核总周期并未改善，不以均值掩盖这一差异。

复现从仓库根目录运行，使用 Python（matplotlib、pymupdf、Pillow）及已有审计输入：

```powershell
python 工具/extract_paper_figure_evidence.py
python 工具/build_six_paper_figures.py
python 工具/build_editable_paper.py
python 工具/render_word_python.py
python 工具/check_word_paper.py
python 工具/audit_supplement_figures.py
python 工具/pdf_layout_audit.py --workspace . --strict
```

当前运行使用 Codex bundled Python，matplotlib/pymupdf 装在 tmp/figure-supplement/deps，构图脚本自动加载。Word 原生渲染依赖本机 Word 与既有 pywin32 环境；LaTeX 在论文目录使用 xelatex -interaction=nonstopmode -halt-on-error -jobname=数模论文 论文正文.tex 三遍。

核验记录见审查/证据/20260926-six-figures。broad-visual-qa 保留第一次宽范围检查的路径解析失败；最终 visual_qa 使用实际编译的输入闭包与编译工作目录解析图路径，范围见 scope.json。正式阶段门禁与 B/C 人工验收未执行。
