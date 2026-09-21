#!/usr/bin/env python3
"""Audit final figure scale, text readability, overlap sidecars, and DrawIO geometry."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older PyMuPDF
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment failure
        raise SystemExit("PyMuPDF is required: pip install PyMuPDF") from exc


MIN_EFFECTIVE_FONT_PT = 9.0
PRIMARY_TARGET_PT = 10.0
LINE_WIDTH_PT = 450.0
TEXT_HEIGHT_PT = 650.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def manuscript_mode(workspace: Path) -> str:
    state = load_json(workspace / "状态" / "工作流状态.json")
    return str(state.get("quality_mode") or state.get("mode") or "baseline")


def latex_files(workspace: Path) -> list[Path]:
    paths = list((workspace / "论文").rglob("*.tex"))
    include_file = workspace / "图表" / "图表引用.tex"
    if include_file.exists():
        paths.append(include_file)
    return sorted(set(paths))


def latex_policy_issues(workspace: Path) -> list[dict]:
    issues = []
    for path in latex_files(workspace):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\\usepackage\s*\[\s*section\s*]\s*\{\s*placeins\s*}", text):
            issues.append({"severity": "critical", "file": path.as_posix(), "kind": "section_placeins", "message": "remove placeins[section]"})
        for match in re.finditer(r"\\begin\{(?:figure|table)\*?}\s*\[([^]]+)]", text):
            spec = match.group(1).strip()
            context = text[max(0, match.start() - 180):match.start()]
            if spec == "H" and "visual-qa: allow-H" not in context:
                line = text.count("\n", 0, match.start()) + 1
                issues.append({"severity": "critical", "file": path.as_posix(), "line": line, "kind": "forced_float", "message": "ordinary figure/table uses [H]; use [!htbp] or document a local exception"})
    return issues


def include_entries(workspace: Path) -> list[dict]:
    entries = []
    pattern = re.compile(r"\\includegraphics(?:\[([^]]*)])?\{([^}]+)}")
    for path in latex_files(workspace):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            entries.append({"tex": path, "options": match.group(1) or "", "asset": match.group(2), "line": text.count("\n", 0, match.start()) + 1})
    return entries


def resolve_asset(workspace: Path, tex_path: Path, raw: str) -> Path | None:
    normalized = raw.replace("\\", "/")
    candidates = [
        tex_path.parent / normalized,
        workspace / normalized,
        workspace / "图表" / Path(normalized).name,
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved
    return None


def option_fraction(options: str, name: str, units: tuple[str, ...]) -> float | None:
    compact = options.replace(" ", "")
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    match = re.search(rf"{name}=([0-9.]+)\\(?:{unit_pattern})", compact)
    return float(match.group(1)) if match else None


def meaningful_text(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) >= 2 or bool(re.search(r"[A-Za-z0-9\u4e00-\u9fff]", stripped))


def vector_asset_metrics(path: Path) -> dict:
    document = fitz.open(path)
    page = document[0]
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text") or "").strip()
                if meaningful_text(text):
                    spans.append({"text": text, "size": float(span.get("size") or 0), "bbox": tuple(float(v) for v in span.get("bbox", (0, 0, 0, 0)))})
    result = {"source_width_pt": float(page.rect.width), "source_height_pt": float(page.rect.height), "text_spans": len(spans)}
    if spans:
        result["minimum_source_font_pt"] = min(span["size"] for span in spans if span["size"] > 0)
        overlap_count = 0
        for index, first in enumerate(spans):
            a = fitz.Rect(first["bbox"])
            for second in spans[index + 1:]:
                b = fitz.Rect(second["bbox"])
                intersection = a & b
                if intersection.is_empty:
                    continue
                smaller = min(max(1.0, a.get_area()), max(1.0, b.get_area()))
                if intersection.get_area() / smaller > 0.02 and intersection.width > 1 and intersection.height > 1:
                    overlap_count += 1
        result["text_overlap_count"] = overlap_count
    document.close()
    return result


def sidecar_for(path: Path) -> Path | None:
    candidates = [path.with_suffix(path.suffix + ".visual.json"), path.with_suffix(".visual.json")]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def audit_asset(workspace: Path, entry: dict, strict: bool) -> dict:
    path = resolve_asset(workspace, entry["tex"], entry["asset"])
    result = {"requested": entry["asset"], "tex": entry["tex"].as_posix(), "line": entry["line"], "issues": []}
    if path is None:
        result["issues"].append({"severity": "critical", "kind": "missing_asset", "message": "included asset does not exist"})
        return result
    result["path"] = path.as_posix()
    result["sha256"] = sha256(path)
    width_fraction = option_fraction(entry["options"], "width", ("linewidth", "textwidth"))
    height_fraction = option_fraction(entry["options"], "height", ("textheight",))
    result["width_fraction"] = width_fraction
    result["height_fraction"] = height_fraction

    metrics = {}
    if path.suffix.lower() == ".pdf":
        try:
            metrics = vector_asset_metrics(path)
        except (RuntimeError, ValueError) as exc:
            result["issues"].append({"severity": "critical", "kind": "unreadable_pdf", "message": str(exc)})
    sidecar = sidecar_for(path)
    if sidecar:
        sidecar_data = load_json(sidecar)
        result["sidecar"] = sidecar.as_posix()
        for key, value in sidecar_data.items():
            if key not in {"issues", "asset"}:
                metrics.setdefault(key, value)
        for issue in sidecar_data.get("issues", []):
            if issue.get("severity") == "critical":
                result["issues"].append(issue)

    source_width = float(metrics.get("source_width_pt") or 0)
    source_height = float(metrics.get("source_height_pt") or 0)
    source_font = float(metrics.get("minimum_source_font_pt") or 0)
    scales = []
    if width_fraction and source_width:
        scales.append(width_fraction * LINE_WIDTH_PT / source_width)
    if height_fraction and source_height:
        scales.append(height_fraction * TEXT_HEIGHT_PT / source_height)
    scale = min(scales) if scales else 1.0
    if source_font:
        effective = source_font * scale
        metrics["estimated_effective_font_pt"] = round(effective, 3)
        if effective < MIN_EFFECTIVE_FONT_PT:
            result["issues"].append({"severity": "critical", "kind": "small_effective_font", "message": f"estimated final font {effective:.2f}pt < {MIN_EFFECTIVE_FONT_PT:.1f}pt"})
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        severity = "critical" if strict else "warning"
        result["issues"].append({"severity": severity, "kind": "unmeasurable_bitmap_text", "message": "bitmap figure has no visual sidecar; final text size cannot be verified"})
    elif metrics.get("text_spans") == 0:
        result["issues"].append({"severity": "warning", "kind": "no_vector_text", "message": "no measurable vector text found"})
    if int(metrics.get("text_overlap_count") or 0) > 0:
        result["issues"].append({"severity": "critical", "kind": "vector_text_overlap", "message": f"{metrics['text_overlap_count']} text bounding-box intersections"})
    result["metrics"] = metrics
    return result


def style_dict(style: str) -> dict[str, str]:
    values = {}
    for token in style.split(";"):
        if "=" in token:
            key, value = token.split("=", 1)
            values[key] = value
    return values


def clean_label(value: str) -> list[str]:
    text = html.unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def rect_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float], pad: float = 1.0) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > pad and min(a[3], b[3]) - max(a[1], b[1]) > pad


def segment_intersects_rect(p1: tuple[float, float], p2: tuple[float, float], rect: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = rect
    for step in range(41):
        ratio = step / 40
        x = p1[0] + (p2[0] - p1[0]) * ratio
        y = p1[1] + (p2[1] - p1[1]) * ratio
        if x1 < x < x2 and y1 < y < y2:
            return True
    return False


def drawio_geometry_issues(path: Path) -> list[dict]:
    issues = []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except ET.ParseError as exc:
        return [{"severity": "critical", "kind": "drawio_xml", "message": str(exc)}]
    cells = {cell.get("id"): cell for cell in root.iter("mxCell") if cell.get("id")}
    children_by_parent: dict[str, list[str]] = {}
    for cell_id, cell in cells.items():
        children_by_parent.setdefault(cell.get("parent", ""), []).append(cell_id)

    local_rects = {}
    for cell_id, cell in cells.items():
        if cell.get("vertex") != "1":
            continue
        geometry = cell.find("mxGeometry")
        if geometry is None:
            continue
        local_rects[cell_id] = tuple(float(geometry.get(key, "0")) for key in ("x", "y", "width", "height"))

    def absolute_rect(cell_id: str, seen: set[str] | None = None):
        seen = seen or set()
        if cell_id in seen or cell_id not in local_rects:
            return None
        seen.add(cell_id)
        x, y, width, height = local_rects[cell_id]
        parent = cells[cell_id].get("parent")
        if parent in local_rects:
            parent_rect = absolute_rect(parent, seen)
            if parent_rect:
                x += parent_rect[0]
                y += parent_rect[1]
        return (x, y, x + width, y + height)

    rects = {cell_id: absolute_rect(cell_id) for cell_id in local_rects}
    rects = {cell_id: rect for cell_id, rect in rects.items() if rect}
    obstacle_ids = [cell_id for cell_id in rects if not children_by_parent.get(cell_id)]
    for index, first_id in enumerate(obstacle_ids):
        for second_id in obstacle_ids[index + 1:]:
            if cells[first_id].get("parent") == cells[second_id].get("parent") and rect_intersects(rects[first_id], rects[second_id]):
                issues.append({"severity": "critical", "kind": "node_overlap", "message": f"nodes {first_id} and {second_id} overlap"})

    for cell_id, rect in rects.items():
        cell = cells[cell_id]
        lines = clean_label(cell.get("value", ""))
        if not lines:
            continue
        style = style_dict(cell.get("style", ""))
        font = float(style.get("fontSize", "11") or 11)
        if font < PRIMARY_TARGET_PT:
            issues.append({"severity": "critical", "kind": "small_node_font", "message": f"node {cell_id} font {font:g}pt < {PRIMARY_TARGET_PT:g}pt"})
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        estimated_width = max(sum(font if "\u4e00" <= char <= "\u9fff" else font * 0.55 for char in line) for line in lines) + 16
        estimated_height = len(lines) * font * 1.35 + 10
        if width < estimated_width or height < estimated_height:
            issues.append({"severity": "critical", "kind": "node_text_overflow", "message": f"node {cell_id} estimated text {estimated_width:.0f}x{estimated_height:.0f}px exceeds {width:.0f}x{height:.0f}px"})

    for edge in (cell for cell in cells.values() if cell.get("edge") == "1"):
        source, target = edge.get("source"), edge.get("target")
        if source not in rects or target not in rects:
            continue
        source_rect, target_rect = rects[source], rects[target]
        points = [((source_rect[0] + source_rect[2]) / 2, (source_rect[1] + source_rect[3]) / 2)]
        geometry = edge.find("mxGeometry")
        if geometry is not None:
            for point in geometry.iter("mxPoint"):
                if point.get("x") is not None and point.get("y") is not None:
                    points.append((float(point.get("x")), float(point.get("y"))))
        points.append(((target_rect[0] + target_rect[2]) / 2, (target_rect[1] + target_rect[3]) / 2))
        for obstacle in obstacle_ids:
            if obstacle in {source, target}:
                continue
            if any(segment_intersects_rect(points[i], points[i + 1], rects[obstacle]) for i in range(len(points) - 1)):
                issues.append({"severity": "critical", "kind": "edge_node_crossing", "message": f"edge {edge.get('id')} crosses node {obstacle}"})
    return issues


def write_markdown(report: dict, path: Path) -> None:
    lines = ["# 图表最终可读性诊断", "", f"- 模式: `{report['mode']}`", f"- 关键问题: {report['critical_count']}", f"- 警告: {report['warning_count']}", "", "| 资产/文件 | 级别 | 类型 | 说明 |", "|---|---|---|---|"]
    for issue in report["latex_issues"]:
        lines.append(f"| {issue['file']} | {issue['severity']} | {issue['kind']} | {issue['message']} |")
    for item in report["figures"] + report["diagrams"]:
        label = item.get("path") or item.get("requested") or "-"
        for issue in item.get("issues", []):
            lines.append(f"| {label} | {issue['severity']} | {issue['kind']} | {issue['message']} |")
    if report["critical_count"] == 0 and report["warning_count"] == 0:
        lines.append("| - | PASS | - | 未发现问题 |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_workspace(workspace: Path, strict: bool = False) -> dict:
    mode = manuscript_mode(workspace)
    strict = strict or mode == "championship"
    latex_issues = latex_policy_issues(workspace)
    figures = [audit_asset(workspace, entry, strict) for entry in include_entries(workspace)]
    diagrams = []
    for path in sorted((workspace / "图表").glob("*.drawio")):
        diagrams.append({"path": path.as_posix(), "sha256": sha256(path), "issues": drawio_geometry_issues(path)})
    all_issues = latex_issues + [issue for item in figures + diagrams for issue in item.get("issues", [])]
    report = {
        "version": 1,
        "mode": mode,
        "strict": strict,
        "thresholds": {"minimum_effective_font_pt": MIN_EFFECTIVE_FONT_PT, "primary_text_target_pt": PRIMARY_TARGET_PT},
        "critical_count": sum(issue.get("severity") == "critical" for issue in all_issues),
        "warning_count": sum(issue.get("severity") == "warning" for issue in all_issues),
        "latex_issues": latex_issues,
        "figures": figures,
        "diagrams": diagrams,
    }
    figure_dir = workspace / "图表"
    figure_dir.mkdir(parents=True, exist_ok=True)
    (figure_dir / "visual_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, figure_dir / "visual_qa.md")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = audit_workspace(args.workspace.resolve(), strict=args.strict)
    print(f"Rendered visual audit: {report['critical_count']} critical, {report['warning_count']} warnings")
    return 1 if report["strict"] and report["critical_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
