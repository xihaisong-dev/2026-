from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "workspace_init.py"
INTAKE = ROOT / "scripts" / "problem_intake.py"
DISCLOSURE = ROOT / "scripts" / "ai_disclosure.py"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode:
        raise RuntimeError(f"failed: {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
    return proc


def load_state(workspace: Path) -> dict:
    return json.loads((workspace / "状态" / "工作流状态.json").read_text(encoding="utf-8"))


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="math-model-ai-disclosure-"))
    problem = base / "problem.txt"
    template = base / "template.doc"
    problem.write_text("problem", encoding="utf-8")
    template.write_text("official template", encoding="utf-8")

    missing = run(
        str(INIT),
        "--workspace", str(base / "missing"),
        "--competition", "gmcm",
        "--problem", str(problem),
        "--template", str(template),
        check=False,
    )
    assert missing.returncode != 0
    assert "--ai-disclosure required|off" in (missing.stdout + missing.stderr)

    workspace = base / "workspace"
    run(
        str(INIT),
        "--workspace", str(workspace),
        "--competition", "gmcm",
        "--problem", str(problem),
        "--template", str(template),
        "--ai-disclosure", "required",
    )
    state = load_state(workspace)
    main_tex = (workspace / "模板" / "当前竞赛" / "main.tex").read_text(encoding="utf-8")
    report = (workspace / "模板" / "当前竞赛" / "sections" / "B_ai_disclosure.tex").read_text(encoding="utf-8")
    assert state["ai_disclosure"]["required"] is True
    assert "\\gmcmaidisclosuretrue" in main_tex
    assert "AI 仅作为辅助手段，模型假设、核心推导、创新点、结果分析由参赛团队独立完成" in report

    repeated_missing = run(
        str(INTAKE),
        "--workspace", str(workspace),
        "--problem", str(problem),
        "--template", str(template),
        check=False,
    )
    assert repeated_missing.returncode != 0
    assert "每次上传赛题" in (repeated_missing.stdout + repeated_missing.stderr)

    run(
        str(DISCLOSURE),
        "--workspace", str(workspace),
        "--mode", "off",
        "--evidence", "manual smoke change",
    )
    state = load_state(workspace)
    main_tex = (workspace / "模板" / "当前竞赛" / "main.tex").read_text(encoding="utf-8")
    assert state["ai_disclosure"]["required"] is False
    assert "\\gmcmaidisclosurefalse" in main_tex

    run(
        str(INTAKE),
        "--workspace", str(workspace),
        "--problem", str(problem),
        "--template", str(template),
        "--ai-disclosure", "required",
    )
    assert load_state(workspace)["ai_disclosure"]["required"] is True
    print(json.dumps({"manual_upload_declaration": "pass", "required": "pass", "off": "pass"}, ensure_ascii=False, indent=2))
    shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
