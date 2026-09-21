from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older PyMuPDF
    import fitz


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "assets" / "shared-scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

from pdf_layout_audit import audit_pdf  # noqa: E402
from rendered_visual_audit import audit_workspace  # noqa: E402


def write_figure(path: Path, fontsize: float) -> None:
    document = fitz.open()
    page = document.new_page(width=432, height=288)
    page.insert_text((72, 120), "Readable model label", fontsize=fontsize)
    document.save(path)
    document.close()


def write_paper(path: Path, sparse_middle: bool) -> None:
    document = fitz.open()
    first = document.new_page(width=595, height=842)
    first.insert_text((90, 120), "Competition Paper", fontsize=24)
    middle = document.new_page(width=595, height=842)
    if sparse_middle:
        middle.insert_text((72, 100), "One stranded sentence", fontsize=12)
    else:
        for index, y in enumerate(range(80, 760, 18)):
            middle.insert_text((72, y), f"Validated model result and interpretation line {index + 1}.", fontsize=12)
    last = document.new_page(width=595, height=842)
    last.insert_text((72, 90), "References", fontsize=16)
    last.insert_text((72, 120), "[1] Example reference.", fontsize=11)
    document.save(path)
    document.close()


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="math-model-visual-layout-"))
    try:
        (workspace / "图表").mkdir(parents=True)
        (workspace / "论文").mkdir(parents=True)
        (workspace / "状态").mkdir(parents=True)
        (workspace / "状态" / "工作流状态.json").write_text(
            json.dumps({"quality_mode": "championship", "output_format": "pdf"}), encoding="utf-8"
        )
        figure = workspace / "图表" / "fig_test.pdf"
        write_figure(figure, 6)
        (workspace / "论文" / "论文正文.tex").write_text(
            "\\usepackage[section]{placeins}\n"
            "\\begin{figure}[H]\\centering\n"
            "\\includegraphics[width=0.72\\linewidth,height=0.70\\textheight,keepaspectratio]{../图表/fig_test.pdf}\n"
            "\\end{figure}\n",
            encoding="utf-8",
        )
        bad_visual = audit_workspace(workspace, strict=True)
        bad_kinds = {
            issue["kind"]
            for issue in bad_visual["latex_issues"]
        } | {
            issue["kind"]
            for item in bad_visual["figures"]
            for issue in item["issues"]
        }
        assert {"section_placeins", "forced_float", "small_effective_font"}.issubset(bad_kinds), bad_visual

        write_figure(figure, 14)
        (workspace / "论文" / "论文正文.tex").write_text(
            "\\begin{figure}[!htbp]\\centering\n"
            "\\includegraphics[width=0.72\\linewidth,height=0.70\\textheight,keepaspectratio]{../图表/fig_test.pdf}\n"
            "\\end{figure}\n",
            encoding="utf-8",
        )
        good_visual = audit_workspace(workspace, strict=True)
        assert good_visual["critical_count"] == 0, good_visual

        paper = workspace / "论文" / "数模论文.pdf"
        write_paper(paper, sparse_middle=True)
        bad_layout = audit_pdf(workspace, paper)
        assert bad_layout["critical_count"] >= 1, bad_layout
        assert any(item["page"] == 2 and item["status"] == "critical" for item in bad_layout["pages"]), bad_layout

        paper.unlink()
        write_paper(paper, sparse_middle=False)
        good_layout = audit_pdf(workspace, paper)
        assert good_layout["critical_count"] == 0, good_layout
        print("visual layout contracts passed")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
