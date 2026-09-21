<p align="center">
  <img src="assets/branding/logo.svg" alt="Meta-model-agent" width="200">
</p>

<h1 align="center">Meta-model-agent</h1>

<p align="center">
  面向数学建模研究与竞赛论文的可执行、可恢复、可审计工作流
</p>

<p align="center">
  <img alt="Workflow" src="https://img.shields.io/badge/Workflow-7%20Stages-0E7490">
  <img alt="Targets" src="https://img.shields.io/badge/Targets-CUMCM%20%7C%2051MCM%20%7C%20MCM%2FICM%20%7C%20NPGMCM-2563A8">
  <img alt="Outputs" src="https://img.shields.io/badge/Outputs-PDF%20%7C%20DOCX-6D4CC3">
  <img alt="VisualQA" src="https://img.shields.io/badge/Visual%20QA-9pt%20%2B%20Zero%20Overlap-C2410C">
  <img alt="Platform" src="https://img.shields.io/badge/Primary-Codex-111827">
  <img alt="Version" src="https://img.shields.io/badge/Version-v3-16A34A">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-16A34A"></a>
</p>

Meta-model-agent 将题意分析、模型构建、真实计算、结果验证、证据可视化、论文写作和提交验收连接为一条工程化研究链。它优先作为 Codex Skill 使用，也可以由能够读取 Markdown 指令、访问工作区并执行本地命令的其他 AI 工具调用。

项目适用于 CUMCM、51MCM、MCM/ICM、NPGMCM（华为杯）及结构相近的数学建模任务。它强调结果可复现、证据一致和**最终渲染质量**——论文图表不仅要在源码里正确，还必须在最终 PDF/DOCX 的 100% 显示比例下可读、无遮挡、无裁切。

> Meta-model-agent 只提供研究辅助。题意、数据、模型、程序、引用、结果、竞赛规则与最终提交材料必须由使用者核验；项目内部评分和门禁不代表竞赛结果承诺。

## 核心能力

- 从真实题面、附件和数据建立问题底稿，并按 `supplied/collected/none` 声明数据模式；
- 有数据时执行题目驱动的数据审计、预处理、质量复核和输入冻结，无数据时明确跳过；
- 将自然语言任务转化为可计算、可验证的数学模型，严格区分模型名称、定制机制与求解算法；
- 先建立可解释基线，再通过对照、消融和稳健性分析验证改进；
- 运行逐问程序并保存结构化结果，使论文数值能够追溯到计算输出；
- 生成数据图、结果表、DrawIO/TikZ 流程图和稳定的论文引用；
- **渲染后视觉审计**：读取最终 PDF 矢量文字与图形几何，检查有效字号、文字重叠、图例压数据、标注压曲线、DrawIO 节点碰撞与文字裁切；
- **PDF 版面诊断**：逐页渲染最终论文，识别正文占用过低、大面积空白带、异常稀疏页等版面问题；
- 按目标竞赛模板组织 LaTeX 或 DOCX 论文，控制摘要结构、正文密度、图表尺寸与页数；
- 从当前源码生成仅包含主程序和逐问核心实现的代码附录，并使用英文程序显示名；
- 通过阶段门禁、返工传播、断点恢复和多轮审稿控制研究质量。

## v3 重点升级：最终渲染质量闭环

v1.2 建立了七阶段工作流和内容合同；v3 在此基础上补上了**"图在源码里好看 ≠ 图在论文里可读"** 的最后一环。图表质量不再依赖生成时的自查，而是在最终嵌入尺寸下接受机器审计：

### 视觉质量合同

新增 [visual-quality-contract.md](references/visual-quality-contract.md)，作为 EVIDENCE、SCHEMATICS、MANUSCRIPT、ASSURANCE 四阶段的统一视觉质量依据：

- 以**最终论文 100% 显示比例下的有效字号**为准，而不是源代码中的 `figsize` 或单图字号；
- 冠军模式下正文图有意义文字不小于 9 pt；坐标轴标签、图例、主要标注和流程图节点目标不小于 10 pt；
- 未批准的文字/图例/数据/标注/节点/连线重叠必须为 0；文字裁切必须为 0；
- 复杂图若不能保持可读性，应拆分、简化或移入附录，不能靠整体缩小解决。

### 渲染后视觉审计

新增 `assets/shared-scripts/rendered_visual_audit.py`（初始化后位于工作区 `工具/`）：

- 审计最终嵌入比例和有效字号，直接读取 PDF 矢量文字位置与字号；
- 读取 Matplotlib 保存时生成的 `*.visual.json` 几何伴随文件，覆盖位图图形；
- 检查文字裁切、文字重叠、图例压住数据、标注压住曲线/数据、DrawIO 节点重叠和连线穿越节点；
- 输出 `图表/visual_qa.json` 与 `图表/visual_qa.md`，支持 `--strict` 严格门禁。

### PDF 空白页诊断

新增 [pdf-layout-diagnostics.md](references/pdf-layout-diagnostics.md) 与 `assets/shared-scripts/pdf_layout_audit.py`：

- 按页渲染最终 PDF，排除页眉、页脚和外边距后分析正文区域；
- 用正文占用行比例、最大连续空白带、尾部空白和有效墨迹识别异常稀疏页（如正文占用低于 45% 或空白带超过正文高度 35% 即可疑）；
- 对封面、末页、参考文献起始页、附录起始页等预期例外显式报告，不静默忽略；
- 生成 `论文/pdf_layout_report.json`、`论文/pdf_layout_report.md` 和可疑页缩略图。

### 内嵌可视化模板

`assets/visual-exemplars/` 内嵌 15 张分类模板图，配 `manifest.json` 逐图登记路径、SHA-256、像素尺寸、布局类型、适用任务与推荐借鉴特征：

| 分类 | 模板 |
| --- | --- |
| 分布 | 配对云雨图、相关矩阵+半边小提琴 |
| 机器学习 | 多分类 SHAP 组合图、交叉验证 ROC、TPE 调参 3D 曲面 |
| 流程图 | 横板任务流水线、三栏阶段流程、三栏研究框架、五带技术路线 |
| 模型评价 | 多模型泰勒图、预测-真实边缘图 |
| 相关性 | 分组环形热力图、相关矩阵组合图、Nature 风格和弦图 |
| 组合图 | 堆叠图+云雨图+箱线图 |

模板只用于借鉴构图、层级、配色和信息组织，且不豁免可读性门禁；流程图模板改为按读者任务、拓扑、密度和最终纵横比选择，不再随机。

### 贯穿性修正

- **绘图工具链**：`plot_utils.py` 提高默认字号并在保存时生成几何伴随文件；`figure_check.py` 拒绝源码中低于 9 pt 的硬编码字号；`drawio_check.py` 拒绝低于 10 pt 的流程图节点字号；
- **LaTeX 浮动体**：普通图表默认 `[!htbp]`，禁止 `\usepackage[section]{placeins}`，`[H]` 仅允许带理由的局部例外，从源头避免空白页和页数膨胀；六套模板已同步修正；
- **门禁集成**：`gate_contracts.py` 在 EVIDENCE/SCHEMATICS/MANUSCRIPT/ASSURANCE 检查视觉 QA 报告，ASSURANCE 另检查 PDF 空白诊断报告；报告必须覆盖当前图形/PDF 哈希且保持新鲜，缺失、陈旧或含关键问题时不得通过冠军模式门禁；
- **回归测试**：新增 `visual_layout_smoke.py`（含 6 pt 小字、强制 `[H]`、`placeins` 反例），冒烟测试增至 13 项，全部通过；完整基线已实际跑通 `rendered_visual_contract`、`final_rendered_visual_contract` 和 `pdf_whitespace_contract` 门禁。

## 工作流

正式工作流由 [机器清单](assets/workflow_manifest.json) 定义，当前包含 7 个阶段：

| 阶段 | 目标 |
| --- | --- |
| `DISCOVERY` | 读取题面、附件与数据，拆解问题并声明数据模式 |
| `FORMULATION` | 建立数学机制、模型身份、预处理合同与验证方案 |
| `COMPUTATION` | 按需预处理数据，编写程序并开展真实计算 |
| `EVIDENCE` | 将结果转化为论文图表与数据证据 |
| `SCHEMATICS` | 绘制技术路线和系统逻辑图 |
| `MANUSCRIPT` | 集成模型、实验、图表、引用与核心代码附录 |
| `ASSURANCE` | 编译并检查内容、版式、视觉质量与最终材料 |

详细的阶段依赖、核验点和产物映射见 [工作流总图](references/workflow-map.md) 与 [门禁矩阵](references/gate-matrix.md)。

## 阶段与质量模式

项目将研究阶段和质量模式作为两个独立维度：

| 维度 | 可选值 | 说明 |
| --- | --- | --- |
| 研究阶段 `phase` | `baseline`、`enhancement` | 默认先完成稳定基线，再对薄弱环节实施受控增强 |
| 质量模式 `mode` | `standard`、`championship` | 默认使用标准模式；冠军模式在论文完成后增加多轮独立审稿并强制视觉/PDF 审计报告 |

切换命令：

```bash
python scripts/pipeline_manager.py set-phase enhancement --workspace ../contest-workspace
python scripts/pipeline_manager.py set-mode championship --workspace ../contest-workspace
```

`enhancement` 不能绕过基线证据。`championship` 至少执行三轮审稿，并应用项目内部的 P0/P1 和综合评分门槛。详细规则见 [阶段控制](references/phase-control.md)、[增强操作](references/enhancement-operations.md) 和 [冠军审稿方法](references/championship-review-method.md)。

## 运行要求

- Python 3.8 或更高版本，建议使用 Python 3.10 或 3.11；
- PDF 路线需要 Bash、XeLaTeX、BibTeX 和相应 TeX 宏包；
- 视觉与 PDF 审计依赖 `PyMuPDF>=1.23.0`（已列入 `scripts/requirements.txt`）；
- DOCX 自动页数门禁需要 LibreOffice，也可登记由 Word 手动导出的 PDF 预览；DrawIO 和 PDF 视觉核验需要对应系统工具；
- 完整的分平台安装、可选建模依赖和自检命令见 [环境配置说明](ENVIRONMENT.md)。

安装 Python 依赖：

```bash
python -m pip install -r scripts/requirements.txt
```

## 快速开始

### 方式一：在 Codex 中配置并直接使用（推荐）

先向 Codex 发送下面的提示词，将项目配置为全局 Skill：

```text
将 https://github.com/lybdora2026/math-model-skills-v2 这个 Skill 直接配置到 Codex 全局 Skill 中。
```

配置完成后，上传赛题、附件和数据，再发送。CUMCM 的使用方式：

```text
开始处理我上传的数学建模赛题。
竞赛类型：CUMCM
模式：冠军模式
论文撰写方式：LaTeX
```

NPGMCM（华为杯）需要同时上传赛题、附件或数据以及当届官方论文模板；当届另有 AI 使用规定或官方说明时，也建议一并上传。然后发送：

```text
开始处理我上传的数学建模赛题。
竞赛类型：NPGMCM（华为杯）
模式：冠军模式
论文撰写方式：LaTeX
AI 使用说明报告：添加
```

若本次不需要在附录中加入 AI 使用说明报告，将最后一行改为 `AI 使用说明报告：不添加`。

华为杯的 AI 使用说明报告是手动开关，每次上传新赛题时都必须主动声明"添加"或"不添加"，不会沿用上一次选择。未上传当届官方论文模板或未声明 AI 开关时，Skill 应先提醒并暂停进入 `DISCOVERY`。华为杯支持 LaTeX 和 Word 两种撰写路线，最终均应按当届要求导出并提交 PDF；Word 路线将上传的当届 `.doc`/`.docx` 官方模板作为底稿，使用时把"论文撰写方式"改为 `Word（DOCX）`。两条路线都要求生成目录，目录最多展示三级标题，禁止四级目录。其他竞赛可按实际任务将竞赛类型改为 `51MCM` 或 `MCM/ICM`。

根目录的 [`SKILL.md`](SKILL.md) 是 Skill 执行入口；运行时应按当前阶段渐进加载协议，而不是一次读取全部参考文件。

### 方式二：使用命令行运行

以下命令均从本仓库根目录执行，`../contest-workspace` 表示独立的目标研究工作区。不要把仓库根目录和研究工作区视为同一目录。

#### 1. 初始化工作区

```bash
python scripts/workspace_init.py --workspace ../contest-workspace --competition cumcm --output-format pdf
```

`--competition` 支持 `cumcm`、`51mcm`、`mcm-icm` 和 `gmcm`（别名：`npgmcm`、`huawei`、`华为杯`）；`--output-format` 支持 `pdf` 和 `docx`。竞赛类型会控制模板、语言、匿名字段、字号和页数门禁。GMCM 的 `docx` 路线要求随赛题上传 `.doc` 或 `.docx` 官方模板。

华为杯初始化必须同时提供赛题和官方论文模板：

```bash
python scripts/workspace_init.py --workspace ../contest-workspace --competition gmcm --output-format pdf --problem ./题目.pdf --template ./论文模板.doc --ai-disclosure required
```

每次上传华为杯赛题都必须主动声明 AI 使用说明开关（`required` 或 `off`），缺少该参数会拒绝导入。选择 `required` 时，除正文附录外还必须填写 `论文/AI使用记录.json`，并让每条记录引用工作区内真实存在的本地证据文件。

#### 2. 查看状态与推进阶段

```bash
python scripts/pipeline_manager.py overview --workspace ../contest-workspace
python scripts/stage_executor.py current --workspace ../contest-workspace
python scripts/stage_executor.py begin DISCOVERY --workspace ../contest-workspace
```

阶段开始后，系统会把当前阶段需要的工具、参考资料和模板同步到目标工作区。完成实际研究工作后，按顺序执行：

```bash
python scripts/stage_executor.py validate DISCOVERY --workspace ../contest-workspace
python scripts/stage_executor.py gate_check DISCOVERY --workspace ../contest-workspace
python scripts/stage_executor.py complete DISCOVERY --workspace ../contest-workspace --artifacts "问题分析.md"
python scripts/stage_executor.py checkpoint DISCOVERY --workspace ../contest-workspace --action approve --note "reviewed"
```

#### 3. 视觉与版面审计

图表生成或嵌入尺寸变化后运行：

```bash
python "../contest-workspace/工具/rendered_visual_audit.py" --workspace ../contest-workspace --strict
```

最终 PDF 编译成功后运行：

```bash
python "../contest-workspace/工具/pdf_layout_audit.py" --workspace ../contest-workspace --strict
python "../contest-workspace/工具/rendered_visual_audit.py" --workspace ../contest-workspace --strict
```

绘图前可先读取模板清单获取构图参考：

```text
参考资料/visual-exemplars/manifest.json
参考资料/visual-quality-contract.md
```

#### 4. DOCX 路线

初始化时选择 `--output-format docx`。论文源稿完成后，使用初始化过程中复制到目标工作区的导出工具：

```bash
python "../contest-workspace/工具/docx_export.py" --workspace ../contest-workspace
```

GMCM DOCX 会校验官方 Word 模板来源哈希，自动插入可更新的 1--3 级目录字段，并通过 PDF 预览核验摘要和正文页数。仅有 Word 时，先在 Word 中手动另存 PDF，再运行 `python 工具/docx_export.py --workspace . --preview-pdf <预览.pdf>` 登记实际页数。

## 文档导航

| 主题 | 文档 |
| --- | --- |
| 环境安装与依赖自检 | [ENVIRONMENT.md](ENVIRONMENT.md) |
| 总流程与阶段映射 | [workflow-map.md](references/workflow-map.md) |
| 阶段门禁与人工核验 | [gate-matrix.md](references/gate-matrix.md) |
| **视觉质量合同** | [visual-quality-contract.md](references/visual-quality-contract.md) |
| **PDF 空白页诊断** | [pdf-layout-diagnostics.md](references/pdf-layout-diagnostics.md) |
| Baseline 与 Enhancement | [phase-control.md](references/phase-control.md) |
| 增强模式操作 | [enhancement-operations.md](references/enhancement-operations.md) |
| 冠军模式审稿与评分 | [championship-review-method.md](references/championship-review-method.md) |
| 主控、工作与复核角色 | [subagent-architecture.md](references/subagent-architecture.md) |
| CUMCM 官方规则摘录 | [cumcm-official-notes.md](references/cumcm-official-notes.md) |
| NPGMCM/GMCM 2025 规则摘录 | [gmcm-2025.md](references/competition-profiles/gmcm-2025.md) |
| GMCM 条件式 AI 使用说明 | [gmcm-ai-disclosure.md](references/gmcm-ai-disclosure.md) |
| 竞赛机器配置 | [competition_profiles.json](assets/competition_profiles.json) |
| 分阶段实施协议 | [`references/stage_protocols/`](references/stage_protocols/) |

目标竞赛的当期正式规则始终高于仓库中的模板、摘录和机器门禁。

## 项目结构

```text
math-model-skills-v2/
├── SKILL.md                  # Skill 入口与总执行规则
├── ENVIRONMENT.md            # 环境安装、依赖分层与自检
├── agents/                   # Skill 界面配置
├── assets/
│   ├── shared-scripts/       # 绘图、审计、校验共享工具
│   ├── templates/            # 四赛制论文模板（LaTeX/DOCX）
│   ├── visual-exemplars/     # 15 张分类图表模板 + manifest 清单
│   └── ...
├── references/               # 工作流指南、质量合同和阶段协议
└── scripts/                  # 初始化、状态机、门禁、审稿和回归脚本
```

初始化后的研究工作区通常包含：

```text
用户数据/  题目/  程序/  图表/  论文/  审查/
状态/      日志/  工具/  参考资料/  模板/
```

## 质量边界

- 自动门禁只能检查已编码的合同，不能证明题意、模型、数据或结论一定正确；
- 矢量 PDF 可直接提取文字估算有效字号；纯位图图形依赖 `plot_utils.py` 的伴随文件，无法测量时冠军模式不得静默豁免；
- 几何重叠检测能发现边界框碰撞，但不能完全判断语义冲突，复杂标注图仍需查看最终 PDF；
- PDF 空白诊断是可解释的启发式筛查，不替代逐页人工验收；
- 外部资料、参考文献、数据集和竞赛规则必须回到原始来源核验；
- `championship` 是内部质量模式名称，不代表获奖、录用或任何第三方评价；
- 最终提交前必须完成人工通读、匿名检查、格式检查和提交确认。

出现中断或上游错误时，先运行 `stage_executor.py status` 和 `pipeline_manager.py next`；需要返工时从对应阶段执行 `rework`，不要只修改最终论文掩盖模型或数据问题。

## 许可与致谢

本项目采用 [MIT License](LICENSE)，允许在保留版权和许可声明的前提下使用、复制、修改、合并、发布、分发、再许可和销售软件副本。

工作流设计参考了 [xuec699-sudo/math-modeling-skills](https://github.com/xuec699-sudo/math-modeling-skills)，并从 **Modex-MH-Agent** 的工作流组织方式中获得部分灵感。本项目为独立设计与实现，与上述项目不存在官方隶属或质量背书关系。

## 赞助支持

<table>
  <tr>
    <td align="center" width="28%">
      <a href="https://88.scxai.top/">
        <img src="assets/branding/sponsor-chuangshi-xinyuan.jpg" alt="创世の鑫元" width="150">
      </a><br>
      <strong>创世の鑫元</strong><br>
      <a href="https://88.scxai.top/">访问官方网站</a>
    </td>
    <td>
      感谢 <strong>创世の鑫元</strong> 对本项目的赞助与支持。其网站提供 AI 相关服务与工具信息；具体服务内容、价格、可用性及使用条款请以官方网站的最新说明为准。
    </td>
  </tr>
</table>
