from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


AI_DISCLOSURE_MODES = ("required", "off")
AI_DISCLOSURE_PENDING = "pending"


def default_ai_disclosure_state(
    profile: dict[str, Any],
    selection: str = AI_DISCLOSURE_PENDING,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    policy = profile.get("ai_disclosure") or {}
    if selection not in (*AI_DISCLOSURE_MODES, AI_DISCLOSURE_PENDING):
        raise ValueError(f"Unknown AI disclosure mode: {selection}")
    if not policy:
        if selection != AI_DISCLOSURE_PENDING:
            raise ValueError("AI disclosure selection is only configurable for a conditional competition profile")
        return {
            "applicable": False,
            "selection": "off",
            "status": "not_applicable",
            "required": False,
            "evidence": [],
        }
    resolved = selection in AI_DISCLOSURE_MODES
    return {
        "applicable": True,
        "selection": selection,
        "status": "resolved" if resolved else "pending",
        "required": selection == "required" if resolved else None,
        "evidence": list(evidence or []),
        "appendix_title": policy.get("appendix_title", "AI 使用说明报告"),
        "template_file": policy.get("template_file", "sections/B_ai_disclosure.tex"),
        "recommended_statement": policy.get("recommended_statement", ""),
    }


def effective_ai_disclosure_mode(state: dict[str, Any]) -> str:
    disclosure = state.get("ai_disclosure") or {}
    if not disclosure:
        return AI_DISCLOSURE_PENDING if state.get("competition") == "gmcm" else "off"
    if not disclosure.get("applicable", False):
        return "off"
    if disclosure.get("status") != "resolved":
        return AI_DISCLOSURE_PENDING
    return "required" if disclosure.get("required") is True else "off"


def configure_main_tex(path: Path, enabled: bool) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    replacement = r"\gmcmaidisclosuretrue" if enabled else r"\gmcmaidisclosurefalse"
    updated, count = re.subn(r"\\gmcmaidisclosure(?:true|false)", lambda _: replacement, text, count=1)
    if count and updated != text:
        path.write_text(updated, encoding="utf-8")
    return bool(count)


def configure_workspace_templates(workspace: Path, state: dict[str, Any]) -> list[str]:
    if state.get("competition") != "gmcm":
        return []
    enabled = effective_ai_disclosure_mode(state) == "required"
    candidates = [
        workspace / "模板" / "当前竞赛" / "main.tex",
        workspace / "论文" / "main.tex",
        workspace / "论文" / "论文正文.tex",
    ]
    return [str(path) for path in candidates if configure_main_tex(path, enabled)]


def main() -> int:
    from state_store import append_event, load_state, save_state

    parser = argparse.ArgumentParser(description="Resolve conditional GMCM AI-use disclosure requirements.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--mode", choices=AI_DISCLOSURE_MODES, required=True)
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Official rule/template path or a concise decision note. Repeat when needed.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    state = load_state(workspace)
    if state.get("competition") != "gmcm":
        raise SystemExit("AI disclosure resolution is only available for GMCM/NPGMCM workspaces.")
    if args.mode in {"required", "off"} and not args.evidence:
        raise SystemExit("Resolving GMCM AI disclosure requires at least one --evidence entry.")

    profile = state.get("competition_profile") or {}
    state["ai_disclosure"] = default_ai_disclosure_state(profile, args.mode, args.evidence)
    save_state(workspace, state)
    updated_files = configure_workspace_templates(workspace, state)
    append_event(
        workspace,
        "ai_disclosure_resolved",
        {
            "mode": args.mode,
            "evidence": args.evidence,
            "updated_templates": updated_files,
        },
    )
    print(
        json.dumps(
            {
                "competition": state.get("competition"),
                "ai_disclosure": state["ai_disclosure"],
                "updated_templates": updated_files,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
