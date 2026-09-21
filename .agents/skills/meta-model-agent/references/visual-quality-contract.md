# Rendered visual quality contract

This contract is the single source of truth for figure and diagram readability in PDF/LaTeX competition papers. Load it in EVIDENCE, SCHEMATICS, MANUSCRIPT, and ASSURANCE whenever figures are produced, embedded, or reviewed.

## Final-output requirements

- Judge readability in the compiled paper at 100% scale, not from `figsize`, source `fontsize`, or the standalone asset alone.
- In championship mode, effective text in a published figure must be at least 9 pt. Axis labels, legends, primary annotations, and flowchart node text target at least 10 pt.
- No meaningful text may be clipped. Unapproved text-text, text-legend, legend-data, annotation-data, node-node, or edge-node intersections are hard failures.
- A figure that becomes unreadable after insertion must be redrawn, simplified, split, or moved. Do not keep shrinking it.
- Ordinary LaTeX floats use `[!htbp]`. `[H]` is permitted only for an explicitly documented local exception. Do not load `placeins` with the `section` option; use deliberate `\FloatBarrier` commands only at real section boundaries where needed.
- Captions carry titles. Do not duplicate a title inside the visual.

## Deterministic QA

Run `python 工具/rendered_visual_audit.py --workspace .` after figure generation and again after manuscript compilation. The command writes `图表/visual_qa.json` and `图表/visual_qa.md`.

The pre-compile pass inspects Matplotlib scripts, DrawIO geometry, standalone vector assets, and LaTeX insertion scale. The post-compile pass inspects the final PDF. Vector text is measured from PDF spans; generated bitmap figures require a `*.visual.json` sidecar or OCR-capable review. Championship mode must not silently waive an unmeasurable published figure.

Machine tolerances exist only for renderer noise: intersections below 1 px or below 2% of the smaller bounding box may be ignored. Semantic overlaps must be zero.

## Visual restraint

- Use white or near-white backgrounds, neutrals, and the smallest semantic color set supported by the data. More than six semantic colors requires a category-based justification.
- Line weights, font weights, and fills establish hierarchy. Do not make all flowchart text bold or all edges equally heavy.
- Prefer one consolidated legend outside dense data regions. Remove redundant legends, repeated axis labels, decorative boxes, shadows, and gradients.
- Composite figures need aligned panels, consistent scales where comparison is intended, and enough physical area for every panel to remain readable.
- Circular heatmaps, chord diagrams, large correlation matrices, and dense research frameworks are allowed only when the final label gate passes. Template membership is not a readability exemption.

## Template references

The bundled examples are under `assets/visual-exemplars/`; read `assets/visual-exemplars/manifest.json` before selecting one. Select by reader task, topology, density, and final aspect ratio. Reuse layout grammar and hierarchy, not source data, wording, captions, or defects.
