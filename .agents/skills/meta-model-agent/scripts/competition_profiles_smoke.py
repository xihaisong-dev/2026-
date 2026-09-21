from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "workspace_init.py"


def run(*args: str) -> None:
    proc = subprocess.run([sys.executable, "-B", "-X", "utf8", *args], text=True, capture_output=True, encoding="utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError(f"failed: {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="math-model-competition-profiles-"))
    expected = {
        "cumcm": {"cumcmthesis.cls", "main.tex"},
        "gmcm": {"gmcmthesis.cls", "main.tex", "cgip_logo.png", "gmcm_logo.png", "huawei_logo.jpeg", "cumt_logo.png"},
        "51mcm": {"51mcmthesis.cls", "main.tex", "LICENSE-CC-BY-NC-4.0.txt", "simkai.ttf", "simsun.ttc", "51mcm.png"},
        "mcm-icm": {"mcmicm.cls", "main.tex"},
    }
    report = {}
    for key, required in expected.items():
        workspace = base / key
        run(str(INIT), "--workspace", str(workspace), "--competition", key)
        state = json.loads((workspace / "状态" / "工作流状态.json").read_text(encoding="utf-8"))
        actual = {path.name for path in (workspace / "模板" / "当前竞赛").iterdir() if path.is_file()}
        assert state["competition"] == key
        assert state["competition_profile"]["template_dir"] == key
        assert required <= actual, (key, required - actual)
        sections = workspace / "模板" / "当前竞赛" / "sections"
        assert sections.exists() and len(list(sections.glob("*.tex"))) >= 9, key
        report[key] = {
            "display_name": state["display_name"],
            "language": state["competition_profile"]["language"],
            "page_limit": state["competition_profile"]["page_limit"],
            "template_files": sorted(actual),
        }
    alias_workspace = base / "gmcm-alias"
    run(str(INIT), "--workspace", str(alias_workspace), "--competition", "npgmcm")
    alias_state = json.loads((alias_workspace / "状态" / "工作流状态.json").read_text(encoding="utf-8"))
    assert alias_state["competition"] == "gmcm"

    source = base / "sample-problem.txt"
    source.write_text("sample problem", encoding="utf-8")
    missing_template = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(INIT), "--workspace", str(base / "gmcm-missing-template"), "--competition", "gmcm", "--problem", str(source), "--ai-disclosure", "off"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert missing_template.returncode != 0
    assert "一并上传" in (missing_template.stdout + missing_template.stderr)

    sample_template = base / "sample-template.doc"
    sample_template.write_text("sample template", encoding="utf-8")
    missing_declaration = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(INIT), "--workspace", str(base / "gmcm-missing-declaration"), "--competition", "gmcm", "--problem", str(source), "--template", str(sample_template)],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert missing_declaration.returncode != 0
    assert "--ai-disclosure required|off" in (missing_declaration.stdout + missing_declaration.stderr)

    declared = base / "gmcm-declared"
    run(str(INIT), "--workspace", str(declared), "--competition", "gmcm", "--problem", str(source), "--template", str(sample_template), "--ai-disclosure", "required")
    declared_state = json.loads((declared / "状态" / "工作流状态.json").read_text(encoding="utf-8"))
    declared_main = (declared / "模板" / "当前竞赛" / "main.tex").read_text(encoding="utf-8")
    assert declared_state["ai_disclosure"]["required"] is True
    assert "\\gmcmaidisclosuretrue" in declared_main

    docx_workspace = base / "gmcm-docx"
    run(str(INIT), "--workspace", str(docx_workspace), "--competition", "gmcm", "--output-format", "docx")
    docx_state = json.loads((docx_workspace / "状态" / "工作流状态.json").read_text(encoding="utf-8"))
    assert docx_state["output_format"] == "docx"
    assert (docx_workspace / "模板" / "当前竞赛" / "论文正文.md").exists()

    non_word_template = base / "sample-template.pdf"
    non_word_template.write_text("not a Word template", encoding="utf-8")
    bad_docx_intake = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(INIT), "--workspace", str(base / "gmcm-docx-non-word"), "--competition", "gmcm", "--output-format", "docx", "--problem", str(source), "--template", str(non_word_template), "--ai-disclosure", "off"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert bad_docx_intake.returncode != 0
    assert ".doc" in (bad_docx_intake.stdout + bad_docx_intake.stderr)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
