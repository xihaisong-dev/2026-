#!/usr/bin/env python3
"""Render a competition PDF and diagnose large, unexplained page whitespace."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older PyMuPDF
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment failure
        raise SystemExit("PyMuPDF is required: pip install PyMuPDF") from exc

try:
    from PIL import Image, ImageFilter
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("Pillow is required: pip install Pillow") from exc


DEFAULTS = {
    "dpi": 180,
    "body_margin_x": 0.07,
    "body_margin_top": 0.075,
    "body_margin_bottom": 0.08,
    "minimum_row_occupancy": 0.45,
    "maximum_blank_band": 0.35,
    "maximum_trailing_blank": 0.40,
    "blank_ink_ratio": 0.0008,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def longest_false_run(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        if value:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def trailing_false_run(values: list[bool]) -> int:
    count = 0
    for value in reversed(values):
        if value:
            break
        count += 1
    return count


def page_exception(page_number: int, page_count: int, text: str) -> str | None:
    normalized = " ".join(text.split()).lower()
    if page_number == 1:
        return "cover_or_first_page"
    if page_number == page_count:
        return "terminal_page"
    opening = normalized[:180]
    if any(token in opening for token in ("参考文献", "references", "bibliography")):
        return "bibliography_start"
    if any(token in opening for token in ("附录", "appendix")):
        return "appendix_start"
    return None


def analyze_page(page, page_number: int, page_count: int, output_dir: Path, cfg: dict) -> dict:
    scale = float(cfg["dpi"]) / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    left = int(image.width * cfg["body_margin_x"])
    right = int(image.width * (1.0 - cfg["body_margin_x"]))
    top = int(image.height * cfg["body_margin_top"])
    bottom = int(image.height * (1.0 - cfg["body_margin_bottom"]))
    body = image.crop((left, top, right, bottom))

    # Dilating dark glyphs converts text lines and graphics into stable occupied bands.
    dark = body.point(lambda value: 255 if value < 242 else 0)
    dilated = dark.filter(ImageFilter.MaxFilter(9))
    width, height = dilated.size
    pixels = dilated.load()
    row_threshold = max(2, int(width * 0.004))
    occupied_rows = []
    dark_pixels = 0
    for y in range(height):
        count = sum(1 for x in range(width) if pixels[x, y] > 0)
        dark_pixels += count
        occupied_rows.append(count >= row_threshold)

    row_occupancy = sum(occupied_rows) / max(1, height)
    blank_band = longest_false_run(occupied_rows) / max(1, height)
    trailing_blank = trailing_false_run(occupied_rows) / max(1, height)
    ink_ratio = dark_pixels / max(1, width * height)
    text = page.get_text("text") or ""
    exception = page_exception(page_number, page_count, text)

    reasons = []
    if ink_ratio < cfg["blank_ink_ratio"]:
        reasons.append("effectively_blank_body")
    if row_occupancy < cfg["minimum_row_occupancy"]:
        reasons.append("low_body_row_occupancy")
    if blank_band > cfg["maximum_blank_band"]:
        reasons.append("large_contiguous_blank_band")
    if trailing_blank > cfg["maximum_trailing_blank"]:
        reasons.append("large_trailing_whitespace")

    # A terminal/start page may be sparse, but an actually blank body remains a defect.
    blocking = bool(reasons) and (exception is None or "effectively_blank_body" in reasons)
    status = "critical" if blocking else "expected_exception" if reasons else "pass"
    thumbnail = None
    if reasons:
        output_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = output_dir / f"page_{page_number:03d}.png"
        preview = image.copy()
        preview.thumbnail((1000, 1400))
        preview.save(thumbnail_path)
        thumbnail = thumbnail_path.as_posix()

    return {
        "page": page_number,
        "status": status,
        "exception": exception,
        "reasons": reasons,
        "metrics": {
            "body_row_occupancy": round(row_occupancy, 4),
            "largest_blank_band": round(blank_band, 4),
            "trailing_blank": round(trailing_blank, 4),
            "dilated_ink_ratio": round(ink_ratio, 5),
        },
        "thumbnail": thumbnail,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# PDF 空白页与版面诊断",
        "",
        f"- PDF: `{report['pdf']}`",
        f"- 页数: {report['page_count']}",
        f"- 关键问题: {report['critical_count']}",
        f"- 预期例外: {report['exception_count']}",
        "",
        "| 页码 | 状态 | 正文行占用 | 最大空白带 | 底部空白 | 原因 |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for item in report["pages"]:
        if item["status"] == "pass":
            continue
        metrics = item["metrics"]
        reason = ", ".join(item["reasons"])
        if item["exception"]:
            reason += f"; exception={item['exception']}"
        lines.append(
            f"| {item['page']} | {item['status']} | {metrics['body_row_occupancy']:.1%} | "
            f"{metrics['largest_blank_band']:.1%} | {metrics['trailing_blank']:.1%} | {reason} |"
        )
    if all(item["status"] == "pass" for item in report["pages"]):
        lines.append("| - | PASS | - | - | - | 未发现可疑空白页 |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_pdf(workspace: Path, pdf_path: Path | None = None, config: dict | None = None) -> dict:
    cfg = dict(DEFAULTS)
    if config:
        cfg.update(config)
    pdf_path = pdf_path or workspace / "论文" / "数模论文.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    diagnostics = workspace / "临时文件" / "pdf_diagnostics"
    document = fitz.open(pdf_path)
    pages = [analyze_page(page, index + 1, len(document), diagnostics, cfg) for index, page in enumerate(document)]
    document.close()
    report = {
        "version": 1,
        "pdf": pdf_path.as_posix(),
        "pdf_sha256": sha256(pdf_path),
        "page_count": len(pages),
        "thresholds": cfg,
        "critical_count": sum(item["status"] == "critical" for item in pages),
        "exception_count": sum(item["status"] == "expected_exception" for item in pages),
        "pages": pages,
    }
    paper_dir = workspace / "论文"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "pdf_layout_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, paper_dir / "pdf_layout_report.md")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = audit_pdf(args.workspace.resolve(), args.pdf.resolve() if args.pdf else None)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"FAIL: {exc}")
        return 2
    print(f"PDF layout audit: {report['critical_count']} critical, {report['exception_count']} expected exceptions")
    return 1 if args.strict and report["critical_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
