"""Regenerate paper-only distribution figures from frozen 500-row ledgers."""

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "图表" / "paper_diagnostics"
OUT.mkdir(exist_ok=True)
Q1 = ROOT / "图表/runs/20260924-A-q1-delivery-r02/all_case_results.csv"
Q2 = ROOT / "图表/runs/20260924-A-q2-delivery-r07/selected_500_rows.csv"
Q3 = ROOT / "图表/runs/20260924-A-q3-delivery-r03/pairs.csv"


def axes(c, x0, y0, w, h, x_ticks, y_ticks, xlabel, ylabel):
    c.setStrokeColor(colors.HexColor("#4B5563"))
    c.line(x0, y0, x0 + w, y0)
    c.line(x0, y0, x0, y0 + h)
    c.setFont("Helvetica", 8)
    for value, x in x_ticks:
        c.line(x, y0, x, y0 - 4)
        c.drawCentredString(x, y0 - 16, str(value))
    for value, y in y_ticks:
        c.line(x0 - 4, y, x0, y)
        c.drawRightString(x0 - 8, y - 3, str(value))
    c.setFont("Helvetica", 9)
    c.drawCentredString(x0 + w / 2, y0 - 32, xlabel)
    c.saveState()
    c.translate(x0 - 42, y0 + h / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, ylabel)
    c.restoreState()


def cdf_plot(q1, q2):
    path = OUT / "five_core_speedup_cdf.pdf"
    c = canvas.Canvas(str(path), pagesize=(480, 285))
    x0, y0, w, h = 58, 52, 382, 190
    x_min, x_max = 1.0, 6.0
    xx = lambda v: x0 + (v - x_min) / (x_max - x_min) * w
    yy = lambda v: y0 + v * h
    axes(c, x0, y0, w, h, [(v, xx(v)) for v in range(1, 7)],
         [(f"{v:.1f}", yy(v)) for v in [0, .25, .5, .75, 1]],
         "Five-core per-case speedup", "Empirical cumulative share")
    for name, data, color in [
        ("Q1 / scenario A", q1, "#1D4E89"),
        ("Q2 / scenario B", q2, "#C96B31"),
    ]:
        values = sorted(data)
        p = c.beginPath()
        p.moveTo(xx(x_min), yy(0))
        for j, value in enumerate(values, 1):
            p.lineTo(xx(min(value, x_max)), yy((j - 1) / len(values)))
            p.lineTo(xx(min(value, x_max)), yy(j / len(values)))
        c.setStrokeColor(colors.HexColor(color))
        c.setLineWidth(2)
        c.drawPath(p)
    c.setFont("Helvetica", 9)
    c.setStrokeColor(colors.HexColor("#1D4E89"))
    c.line(265, 82, 285, 82)
    c.drawString(291, 79, "Q1 / scenario A")
    c.setStrokeColor(colors.HexColor("#C96B31"))
    c.line(265, 68, 285, 68)
    c.drawString(291, 65, "Q2 / scenario B")
    c.save()


def gain_plot(q3):
    path = OUT / "five_core_l2_ratio.pdf"
    c = canvas.Canvas(str(path), pagesize=(480, 285))
    x0, y0, w, h = 58, 52, 382, 190
    bins = [1, 1.000001, 1.01, 1.02, 1.04, 1.08, 1.20]
    counts = []
    for j in range(len(bins) - 1):
        if j == len(bins) - 2:
            count = sum(bins[j] <= x <= bins[j + 1] for x in q3)
        else:
            count = sum(bins[j] <= x < bins[j + 1] for x in q3)
        counts.append(count)
    max_count = max(counts)
    yy = lambda v: y0 + v / 40 * h
    axes(c, x0, y0, w, h,
         [(label, x0 + (j + .5) * w / len(counts)) for j, label in enumerate(
             ["=1", "(1,1.01)", "[1.01,1.02)", "[1.02,1.04)", "[1.04,1.08)", ">=1.08"])],
         [(str(v), yy(v)) for v in [0, 10, 20, 30, 40]],
         "No-L2 / optimized-L2 time ratio", "Number of cases")
    bar_w = w / len(counts) - 8
    c.setFillColor(colors.HexColor("#237F76"))
    for j, count in enumerate(counts):
        x = x0 + j * w / len(counts) + 4
        c.rect(x, y0, bar_w, yy(count) - y0, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1F2937"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + bar_w / 2, yy(count) + 5, str(count))
        c.setFillColor(colors.HexColor("#237F76"))
    c.save()
    assert sum(counts) == len(q3)


def main():
    q1 = pd.read_csv(Q1)
    q2 = pd.read_csv(Q2)
    q3 = pd.read_csv(Q3)
    a = q1.loc[q1.cores == 5, "speedup"].tolist()
    b = q2.loc[q2.cores == 5, "speedup"].tolist()
    g = q3.loc[q3.cores == 5, "combined_ratio"].tolist()
    assert len(a) == len(b) == len(g) == 100
    cdf_plot(a, b)
    gain_plot(g)
    print(OUT)


if __name__ == "__main__":
    main()
