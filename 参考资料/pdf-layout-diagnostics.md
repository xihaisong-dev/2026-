# PDF layout diagnostics

Load this reference in MANUSCRIPT and ASSURANCE for PDF/LaTeX output.

## Required command

After every successful final compilation, run:

```bash
python 工具/pdf_layout_audit.py --workspace . --strict
python 工具/rendered_visual_audit.py --workspace . --strict
```

The PDF audit writes `论文/pdf_layout_report.json`, `论文/pdf_layout_report.md`, and thumbnails for suspect pages under `临时文件/pdf_diagnostics/`. Reports must be newer than the compiled PDF.

## Page classification

The detector analyzes the usable body region after excluding stable header, footer, and outer margins. It uses raster row occupancy and contiguous blank bands rather than raw dark-pixel percentage, because ordinary text naturally has a low ink ratio.

A page is suspicious when any of these conditions holds:

- occupied body-row ratio is below 45%;
- the largest contiguous vertical blank band exceeds 35% of usable body height;
- trailing body whitespace exceeds 40% on a non-terminal content page;
- the body is effectively blank.

Cover pages, intentional blank verso pages, the final page, and pages beginning a bibliography or appendix are classified as expected exceptions. They remain visible in the report and are never silently discarded.

## Root-cause repair order

For each non-exempt suspect page, inspect the TeX source and repair in this order:

1. Replace ordinary `[H]` with `[!htbp]`.
2. Remove `\usepackage[section]{placeins}` and unnecessary `\FloatBarrier`, `\clearpage`, `\newpage`, or oversized `\Needspace`.
3. Crop whitespace inside figure assets.
4. Reduce only genuinely oversized figures while keeping the effective font floor.
5. Move a float earlier or later, split an over-tall composite, or summarize a long table.

Do not fill a sparse page by enlarging figures, increasing line spacing, or adding generic prose.

## Gate semantics

In championship mode, any non-exempt suspicious page or stale/missing report is a hard failure. Other modes may surface borderline pages as warnings, but blank pages and ordinary `[H]`/`placeins[section]` violations remain failures.

