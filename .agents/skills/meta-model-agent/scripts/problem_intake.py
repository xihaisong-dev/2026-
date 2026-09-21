from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from ai_disclosure import AI_DISCLOSURE_MODES, configure_workspace_templates, default_ai_disclosure_state, effective_ai_disclosure_mode
from manifest import normalize_competition
from state_store import append_event, load_state, save_state


PROBLEM_ROOT = Path("题目")
PROBLEM_FILES_ROOT = PROBLEM_ROOT / "赛题原件"
TEMPLATE_FILES_ROOT = PROBLEM_ROOT / "官方论文模板"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_source(source: Path, destination_root: Path) -> Path:
    source = source.resolve()
    if not source.exists():
        raise SystemExit(f"input does not exist: {source}")
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / source.name
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    elif source != destination.resolve():
        shutil.copy2(source, destination)
    return destination


def _records(workspace: Path, paths: Iterable[Path]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for root in paths:
        candidates = sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else [root]
        for path in candidates:
            records.append({
                "path": path.relative_to(workspace).as_posix(),
                "sha256": _sha256(path),
            })
    return records


def uploaded_problem_files(workspace: Path) -> list[Path]:
    root = workspace / PROBLEM_FILES_ROOT
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def uploaded_template_files(workspace: Path) -> list[Path]:
    root = workspace / TEMPLATE_FILES_ROOT
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def contains_word_template(path: Path) -> bool:
    path = path.resolve()
    if not path.exists():
        return False
    candidates = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    return any(item.suffix.lower() in {".doc", ".docx"} for item in candidates)


def competition_input_issues(workspace: Path, state: dict[str, Any]) -> list[str]:
    competition = normalize_competition(state.get("competition", "cumcm"))
    intake = state.get("problem_intake") or {}
    if competition != "gmcm":
        return []
    problem_files = uploaded_problem_files(workspace)
    template_files = uploaded_template_files(workspace)
    if not problem_files and intake.get("problem_files"):
        problem_files = [workspace / item["path"] for item in intake["problem_files"] if (workspace / item["path"]).exists()]
    if not template_files and intake.get("template_files"):
        template_files = [workspace / item["path"] for item in intake["template_files"] if (workspace / item["path"]).exists()]
    issues: list[str] = []
    if not problem_files:
        issues.append("华为杯 DISCOVERY 需要先上传赛题原件（使用 problem_intake.py --problem）")
    if not template_files:
        issues.append("华为杯要求赛题与官方论文模板一并上传；未检测到模板，请使用 --template 提供官方模板")
    if state.get("output_format") == "docx" and template_files and not any(path.suffix.lower() in {".doc", ".docx"} for path in template_files):
        issues.append("华为杯 DOCX 路线需要上传 .doc 或 .docx 官方论文模板，其他格式只能作为规则参考")
    if effective_ai_disclosure_mode(state) == "pending":
        issues.append("华为杯上传赛题时必须主动声明 AI 使用说明开关：--ai-disclosure required|off")
    return issues


def ingest_problem_inputs(
    workspace: Path,
    state: dict[str, Any],
    problem_paths: list[str],
    template_path: str | None,
    ai_disclosure: str | None = None,
) -> dict[str, Any]:
    competition = normalize_competition(state.get("competition", "cumcm"))
    profile = state.get("competition_profile", {})
    requires_template = bool(profile.get("problem_intake", {}).get("requires_template_upload", False))
    if not problem_paths:
        raise SystemExit("at least one --problem input is required")
    if requires_template and not template_path:
        raise SystemExit("华为杯要求上传赛题时一并上传官方论文模板，请使用 --template <template-file-or-directory>")
    if competition == "gmcm" and ai_disclosure not in AI_DISCLOSURE_MODES:
        raise SystemExit("华为杯每次上传赛题时必须主动声明 AI 使用说明开关：--ai-disclosure required|off")
    if competition == "gmcm" and state.get("output_format") == "docx" and template_path and not contains_word_template(Path(template_path)):
        raise SystemExit("华为杯 DOCX 路线需要通过 --template 上传 .doc 或 .docx 官方论文模板")

    imported_problems = [_copy_source(Path(raw), workspace / PROBLEM_FILES_ROOT) for raw in problem_paths]
    imported_templates = [_copy_source(Path(template_path), workspace / TEMPLATE_FILES_ROOT)] if template_path else []
    template_records = _records(workspace, imported_templates)
    if competition == "gmcm" and state.get("output_format") == "docx":
        word_templates = [item for item in template_records if Path(item["path"]).suffix.lower() in {".doc", ".docx"}]
        if not word_templates:
            raise SystemExit("华为杯 DOCX 路线需要通过 --template 上传 .doc 或 .docx 官方论文模板")
    intake = {
        "status": "complete" if imported_problems and (imported_templates or not requires_template) else "pending",
        "template_required": requires_template,
        "problem_files": _records(workspace, imported_problems),
        "template_files": template_records,
        "template_source": "uploaded" if imported_templates else None,
        "warnings": [] if imported_templates or not requires_template else ["official paper template is missing"],
    }
    state["problem_intake"] = intake
    if competition == "gmcm":
        state["ai_disclosure"] = default_ai_disclosure_state(
            profile,
            str(ai_disclosure),
            [f"manual declaration accompanying problem upload: {ai_disclosure}"],
        )
    save_state(workspace, state)
    configure_workspace_templates(workspace, state)
    append_event(
        workspace,
        "problem_intake",
        {"competition": competition, "ai_disclosure": state.get("ai_disclosure"), **intake},
    )
    print(json.dumps({"competition": competition, "ai_disclosure": state.get("ai_disclosure"), **intake}, ensure_ascii=False, indent=2))
    return intake


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a competition problem and its official paper template into a research workspace.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--problem", action="append", required=True, help="Problem statement file; repeat for multiple files.")
    parser.add_argument("--template", help="Official paper template file or directory. Required for GMCM/NPGMCM.")
    parser.add_argument("--ai-disclosure", choices=AI_DISCLOSURE_MODES, help="Required for every GMCM problem upload.")
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    state = load_state(workspace)
    ingest_problem_inputs(workspace, state, args.problem, args.template, args.ai_disclosure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
