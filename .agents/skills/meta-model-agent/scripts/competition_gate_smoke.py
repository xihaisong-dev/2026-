from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from gate_contracts import (  # noqa: E402
    GateResult,
    anonymous_markers,
    competition_source_checks,
    count_section_files,
    declared_base_font_pt,
    has_section_inputs,
    quality_page_target_check,
)


def complete_ai_disclosure(workspace: Path) -> None:
    report_path = workspace / "论文" / "sections" / "B_ai_disclosure.tex"
    report = report_path.read_text(encoding="utf-8")
    replacements = {
        "[填写工具名称]": "Codex",
        "[填写提供方]": "OpenAI",
        "[填写型号或版本]": "GPT-5.6",
        "[填写日期]": "2026-08-29",
        "[仅填写实际发生的辅助用途]": "检查论文模型表述与章节逻辑",
        "[填写实际环节]": "模型表述复核",
        "[概述提示、检索、语言或代码辅助，不粘贴无关长对话]": "复核问题一模型名称与求解算法的区分",
        "[说明团队的判断、计算、修改和验证]": "团队对照建模报告和计算结果逐条复核",
        "[填写关键交互摘要]": "复核问题一模型名称与求解算法的区分",
        "[采纳/部分采纳/未采纳]": "部分采纳",
        "[填写人工修改、独立验证及判断依据]": "团队逐条核对后改写模型名称，并对照建模报告和计算结果复核",
    }
    for source, target in replacements.items():
        report = report.replace(source, target)
    report_path.write_text(report, encoding="utf-8")
    evidence_path = workspace / "日志" / "AI使用证据" / "record-1.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("模型表述复核记录：团队对照建模报告和计算结果完成核验。", encoding="utf-8")
    ledger = {
        "responsibility_confirmed": True,
        "truthfulness_confirmed": True,
        "records": [{
            "tool": "Codex",
            "provider": "OpenAI",
            "model_version": "GPT-5.6",
            "date": "2026-08-29",
            "stage": "模型表述复核",
            "purpose": "检查论文模型表述与章节逻辑",
            "interaction_summary": "复核问题一模型名称与求解算法的区分",
            "adoption": "部分采纳",
            "human_revision": "团队逐条核对后改写模型名称",
            "verification": "对照建模报告和计算结果复核",
            "evidence_refs": ["日志/AI使用证据/record-1.txt"],
        }],
    }
    (workspace / "论文" / "AI使用记录.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    profiles = json.loads((ROOT / "assets" / "competition_profiles.json").read_text(encoding="utf-8"))
    base = Path(tempfile.mkdtemp(prefix="math-model-competition-gate-"))
    results = {}
    for key, profile in profiles.items():
        source = ROOT / "assets" / "templates" / "manuscript-synthesis" / profile["template_dir"]
        paper = base / key / "论文"
        shutil.copytree(source, paper)
        main_tex = (paper / "main.tex").read_text(encoding="utf-8")
        class_text = (paper / profile["class_file"]).read_text(encoding="utf-8")
        font_pt = declared_base_font_pt(main_tex, class_text)
        missing_contracts = [term for term in profile["class_required_terms"] if term.lower() not in class_text.lower()]
        assert count_section_files(base / key) >= 9, key
        assert has_section_inputs(main_tex), key
        assert font_pt is not None and font_pt >= float(profile["minimum_font_pt"]), (key, font_pt)
        assert not missing_contracts, (key, missing_contracts)
        if key == "cumcm":
            assert "\\tableofcontents" not in main_tex
            for marker in ("AbstractStart", "AbstractEnd", "BodyStart", "BodyEnd"):
                assert f"\\label{{{marker}}}" in main_tex, marker
        state_dir = base / key / "状态"
        state_dir.mkdir(parents=True, exist_ok=True)
        state = {"competition": key}
        if key == "gmcm":
            state["ai_disclosure"] = {"applicable": True, "selection": "off", "status": "resolved", "required": False, "evidence": ["smoke"]}
        (state_dir / "工作流状态.json").write_text(json.dumps(state), encoding="utf-8")
        if key == "mcm-icm":
            main_tex = main_tex.replace("\\controlnumber{[CONTROL NUMBER]}", "\\controlnumber{1234567}")
            main_tex = main_tex.replace("\\problemchoice{[A--F]}", "\\problemchoice{A}")
        corpus = main_tex + "\n" + "\n".join(path.read_text(encoding="utf-8") for path in (paper / "sections").glob("*.tex"))
        gate = GateResult("MANUSCRIPT", "competition-smoke")
        competition_source_checks(base / key, main_tex, corpus, gate)
        assert gate.to_dict()["passed"], (key, gate.to_dict()["issues"])
        if key == "gmcm":
            assert "\\tableofcontents" in main_tex
            bad_main = main_tex + "\n\\paragraph{Forbidden level four heading}\n"
            bad = GateResult("MANUSCRIPT", "competition-smoke-toc-negative")
            competition_source_checks(base / key, bad_main, bad_main, bad)
            assert not bad.to_dict()["passed"]
            assert any("competition_toc_max_depth" in issue for issue in bad.to_dict()["issues"])
            required_state = dict(state)
            required_state["ai_disclosure"] = {"applicable": True, "selection": "required", "status": "resolved", "required": True, "evidence": ["smoke"]}
            (state_dir / "工作流状态.json").write_text(json.dumps(required_state), encoding="utf-8")
            required_main = main_tex.replace("\\gmcmaidisclosurefalse", "\\gmcmaidisclosuretrue")
            complete_ai_disclosure(base / key)
            required_corpus = required_main + "\n" + "\n".join(path.read_text(encoding="utf-8") for path in (paper / "sections").glob("*.tex"))
            required_gate = GateResult("MANUSCRIPT", "competition-smoke-ai-required")
            competition_source_checks(base / key, required_main, required_corpus, required_gate)
            assert required_gate.to_dict()["passed"], required_gate.to_dict()["issues"]
            report_path = paper / "sections" / "B_ai_disclosure.tex"
            complete_report = report_path.read_text(encoding="utf-8")
            report_path.write_text(complete_report.replace("Codex", "[填写工具名称]", 1), encoding="utf-8")
            placeholder_gate = GateResult("MANUSCRIPT", "competition-smoke-ai-placeholder-negative")
            competition_source_checks(base / key, required_main, required_corpus, placeholder_gate)
            assert not placeholder_gate.to_dict()["passed"]
            assert any("gmcm_ai_disclosure_placeholders" in issue for issue in placeholder_gate.to_dict()["issues"])
            report_path.write_text(complete_report, encoding="utf-8")
            ledger_path = paper / "AI使用记录.json"
            ledger_text = ledger_path.read_text(encoding="utf-8")
            ledger_path.unlink()
            missing_evidence = GateResult("MANUSCRIPT", "competition-smoke-ai-evidence-negative")
            competition_source_checks(base / key, required_main, required_corpus, missing_evidence)
            assert not missing_evidence.to_dict()["passed"]
            assert any("gmcm_ai_disclosure_evidence" in issue for issue in missing_evidence.to_dict()["issues"])
            ledger_path.write_text(ledger_text, encoding="utf-8")
            coarse_path = paper / "sections" / "5_problem1.tex"
            original_problem = coarse_path.read_text(encoding="utf-8")
            coarse_path.write_text("\\section{问题一模型的建立与求解}\n只有笼统正文。\n", encoding="utf-8")
            coarse = GateResult("MANUSCRIPT", "competition-smoke-toc-coarse")
            competition_source_checks(base / key, required_main, corpus, coarse)
            assert not coarse.to_dict()["passed"]
            assert any("competition_toc_problem_structure" in issue for issue in coarse.to_dict()["issues"])
            coarse_path.write_text(original_problem, encoding="utf-8")
        results[key] = {"font_pt": font_pt, "sections": count_section_files(base / key), "class_contracts": "pass"}

    assert "University" not in anonymous_markers("Oxford University Press")
    assert "Advisor" not in anonymous_markers("Advisor-based optimization is discussed as a method name.")
    assert declared_base_font_pt("\\documentclass[10pt]{article}", "") == 10.0
    assert declared_base_font_pt("\\documentclass[12pt]{article}", "") == 12.0

    gmcm_profile = profiles["gmcm"]
    standard_target = GateResult("ASSURANCE", "page-target-standard")
    quality_page_target_check({"quality_mode": "standard"}, gmcm_profile, 20, standard_target)
    assert standard_target.to_dict()["passed"] and standard_target.to_dict()["warnings"]
    championship_short = GateResult("ASSURANCE", "page-target-championship-short")
    quality_page_target_check({"quality_mode": "championship"}, gmcm_profile, 29, championship_short)
    assert not championship_short.to_dict()["passed"]
    championship_pass = GateResult("ASSURANCE", "page-target-championship-pass")
    quality_page_target_check({"quality_mode": "championship"}, gmcm_profile, 30, championship_pass)
    assert championship_pass.to_dict()["passed"]

    mcm_workspace = base / "mcm-icm"
    mcm_class = mcm_workspace / "论文" / "mcmicm.cls"
    original = mcm_class.read_text(encoding="utf-8")
    mcm_class.write_text(original.replace("LoadClass[12pt,letterpaper]", "LoadClass[10pt,letterpaper]"), encoding="utf-8")
    main_tex = (mcm_workspace / "论文" / "main.tex").read_text(encoding="utf-8").replace("\\controlnumber{[CONTROL NUMBER]}", "\\controlnumber{1234567}").replace("\\problemchoice{[A--F]}", "\\problemchoice{A}")
    corpus = main_tex + "\nReport on Use of AI Tools\nsummarysheet keywords thebibliography"
    negative = GateResult("MANUSCRIPT", "competition-smoke-negative")
    competition_source_checks(mcm_workspace, main_tex, corpus, negative)
    assert not negative.to_dict()["passed"]
    assert any("competition_minimum_font" in issue or "competition_class_contract" in issue for issue in negative.to_dict()["issues"])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
