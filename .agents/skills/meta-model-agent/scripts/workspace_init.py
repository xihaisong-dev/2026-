from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_disclosure import AI_DISCLOSURE_MODES, AI_DISCLOSURE_PENDING, configure_workspace_templates
from manifest import SKILL_ROOT, competition_choices, competition_profile, load_competition_profiles, load_manifest, normalize_competition
from problem_intake import ingest_problem_inputs
from state_store import ensure_workspace_dirs, init_state


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if "__pycache__" in rel.parts or item.suffix.lower() in {".pyc", ".pyo", ".bak"}:
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def parse_competition(raw: str) -> str:
    try:
        return normalize_competition(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a Meta-model-agent mathematical modeling research workspace.")
    parser.add_argument("--workspace", default=".", help="Target workspace directory. Default: current directory.")
    parser.add_argument("--title", default="Meta-model-agent", help="Human-readable workflow title.")
    parser.add_argument("--competition", type=parse_competition, choices=sorted(load_competition_profiles()), default="cumcm", help=f"Strict competition template/profile. Aliases: {', '.join(competition_choices())}.")
    parser.add_argument("--output-format", choices=["pdf", "docx"], default="pdf", help="Final paper artifact format.")
    parser.add_argument("--problem", action="append", default=[], help="Problem statement file to import. Repeat for multiple attachments.")
    parser.add_argument("--template", help="Official competition paper template to import with --problem.")
    parser.add_argument(
        "--ai-disclosure",
        choices=AI_DISCLOSURE_MODES,
        help="Required GMCM declaration when importing a problem: required or off.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing 工作流状态.json.")
    args = parser.parse_args()

    profile = competition_profile(args.competition)
    supported_formats = profile.get("supported_output_formats", ["pdf", "docx"])
    if args.output_format not in supported_formats:
        raise SystemExit(f"{profile['display_name']} currently supports: {', '.join(supported_formats)}; requested: {args.output_format}")
    if args.template and not args.problem:
        parser.error("--template must be supplied together with at least one --problem")
    if args.competition != "gmcm" and args.ai_disclosure is not None:
        parser.error("--ai-disclosure is only configurable for GMCM/NPGMCM")
    if args.competition == "gmcm" and args.problem and args.ai_disclosure is None:
        parser.error("GMCM problem upload requires --ai-disclosure required|off")
    ai_disclosure = args.ai_disclosure or AI_DISCLOSURE_PENDING

    workspace = Path(args.workspace).resolve()
    ensure_workspace_dirs(workspace)
    copy_tree(SKILL_ROOT / "assets" / "shared-scripts", workspace / "工具")
    shutil.copy2(SKILL_ROOT / "scripts" / "docx_export.py", workspace / "工具" / "docx_export.py")
    shutil.copy2(SKILL_ROOT / "scripts" / "build_code_appendix.py", workspace / "工具" / "build_code_appendix.py")
    references_dir = workspace / "参考资料"
    references_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SKILL_ROOT / "references" / "visual-quality-contract.md", references_dir / "visual-quality-contract.md")
    shutil.copy2(SKILL_ROOT / "references" / "pdf-layout-diagnostics.md", references_dir / "pdf-layout-diagnostics.md")
    copy_tree(SKILL_ROOT / "assets" / "visual-exemplars", references_dir / "visual-exemplars")
    template_source = SKILL_ROOT / "assets" / "templates" / "manuscript-synthesis" / profile["template_dir"]
    copy_tree(template_source, workspace / "模板" / "当前竞赛")
    if args.output_format == "docx":
        copy_tree(SKILL_ROOT / "assets" / "templates" / "docx" / args.competition, workspace / "模板" / "当前竞赛")
    state = init_state(
        workspace,
        title=args.title,
        competition=args.competition,
        output_format=args.output_format,
        ai_disclosure=ai_disclosure,
        force=args.force,
    )
    configure_workspace_templates(workspace, state)
    if args.problem:
        ingest_problem_inputs(workspace, state, args.problem, args.template, args.ai_disclosure)

    print(f"[init] workspace: {workspace}")
    print(f"[init] phase: {state['phase']}")
    print(f"[init] competition: {state['competition']} ({state['display_name']})")
    print(f"[init] output format: {state['output_format']}")
    if state.get("competition") == "gmcm":
        print(f"[init] AI disclosure: {state['ai_disclosure']['selection']} ({state['ai_disclosure']['status']})")
    print(f"[init] current stage: {state['current_stage_id']}")
    print("[init] directories:")
    for rel in load_manifest()["workspace_dirs"]:
        print(f"  - {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
