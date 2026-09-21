# LaTeX figure contract

This file is the authoritative LaTeX figure-sizing and float-policy source. When another protocol conflicts with it, this file wins. Also load `../visual-quality-contract.md` for rendered readability thresholds.

- Every `\includegraphics` must have bounded width or height and `keepaspectratio`.
- Default ordinary figure: `width=0.72\linewidth,height=0.70\textheight,keepaspectratio`.
- Square or portrait figure: normally `0.55--0.72\linewidth`.
- Wide time-series or heatmap: normally `0.80--0.90\linewidth`.
- Width must not exceed `1.0\linewidth`/`1.0\textwidth`; height must not exceed `0.70\textheight`.
- If labels become unreadable, redraw, simplify, split, or move the figure; do not keep shrinking it.
- Overfull boxes, clipped graphics, distorted aspect ratios, and unconstrained `\includegraphics{...}` are hard failures.
- Ordinary figures use `[!htbp]`. `[H]` requires a nearby `% visual-qa: allow-H reason=...` exception comment.
- Do not use `\usepackage[section]{placeins}`. Insert `\FloatBarrier` only at deliberate boundaries after checking the compiled page result.
- Final effective text is measured after LaTeX scaling: all meaningful figure text must be at least 9 pt in championship mode; axes labels, legends, primary annotations, and flowchart node text target at least 10 pt.
- Run `python 工具/rendered_visual_audit.py --workspace . --strict` after figures or insertion sizes change.
