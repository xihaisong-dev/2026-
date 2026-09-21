#!/usr/bin/env python3
"""Cross-platform state, gate, and SHA-256 freeze helper for math-model contests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "3.0"
GATES = ("rules-problem", "retrieval", "protocol", "tournament", "model-results", "paper")
FREEZE_NAMES = {
    "protocol": "tournament_protocol",
    "model-results": "model_results",
    "paper": "paper",
}
FREEZE_DEPENDENCY = {
    "problem": None,
    "tournament_protocol": "problem",
    "model_results": "tournament_protocol",
    "paper": "model_results",
}
IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", "_tmp"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {candidate}") from exc
    return resolved


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def iter_files(root: Path, inputs: Iterable[str]) -> list[Path]:
    found: dict[str, Path] = {}
    for raw in inputs:
        target = inside(root, root / raw)
        if not target.exists():
            raise FileNotFoundError(f"freeze input does not exist: {raw}")
        candidates = [target] if target.is_file() else target.rglob("*")
        for path in candidates:
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if any(part in IGNORED_PARTS for part in relative.parts):
                continue
            found[relative.as_posix()] = path
    return [found[key] for key in sorted(found)]


def result(name: str, errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": name,
        "status": "FAIL" if errors else "PASS",
        "checked_at": now_iso(),
        "errors": errors,
        "warnings": warnings or [],
    }


def load_required(root: Path, relative: str, errors: list[str]) -> dict[str, Any] | None:
    path = root / relative
    if not path.is_file():
        errors.append(f"missing required file: {relative}")
        return None
    try:
        return read_json(path)
    except Exception as exc:  # noqa: BLE001 - diagnostics must be recorded
        errors.append(f"invalid JSON {relative}: {exc}")
        return None


def nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def check_rules_problem(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    rules = load_required(root, "00_admin/rules.json", errors)
    inputs = load_required(root, "00_admin/input_manifest.json", errors)
    semantic = load_required(root, "00_admin/semantic_contract.json", errors)
    for name, data in (("rules", rules), ("input manifest", inputs), ("semantic contract", semantic)):
        if data is not None and data.get("status") != "PASS":
            errors.append(f"{name} status is not PASS")
    if rules is not None:
        if not nonempty(rules.get("official_source")) or not nonempty(rules.get("retrieved_at")):
            errors.append("official rules source/time is missing")
        for field in ("template", "ai_policy", "submission_requirements"):
            item = rules.get(field)
            if not isinstance(item, dict) or item.get("status") != "PASS":
                errors.append(f"rules.{field} is not PASS")
        template = rules.get("template")
        if isinstance(template, dict) and template.get("status") == "PASS":
            if not all(nonempty(template.get(field)) for field in ("source", "path", "sha256")):
                errors.append("rules.template lacks source/path/sha256")
            else:
                try:
                    template_path = inside(root, root / str(template["path"]))
                    if not template_path.is_file():
                        errors.append(f"official template file missing: {template['path']}")
                    elif sha256(template_path).lower() != str(template["sha256"]).lower():
                        errors.append(f"official template hash mismatch: {template['path']}")
                except ValueError as exc:
                    errors.append(str(exc))
    if inputs is not None:
        files = inputs.get("files")
        allowed_classes = {"official", "provided_example", "author_collected"}
        workflow_path = root / "00_admin/workflow.json"
        if workflow_path.is_file():
            try:
                allowed_classes = set(read_json(workflow_path).get("formal_data_classes", allowed_classes))
            except Exception:
                pass
        if not isinstance(files, list) or not files:
            errors.append("input manifest has no files")
        else:
            for item in files:
                if not isinstance(item, dict) or not all(nonempty(item.get(key)) for key in ("path", "role", "data_class", "source", "sha256")):
                    errors.append("input manifest contains an incomplete file entry")
                    continue
                if item.get("data_class") not in allowed_classes:
                    errors.append(f"non-formal input class: {item.get('path')} -> {item.get('data_class')}")
                if item.get("provenance_status") != "VERIFIED":
                    errors.append(f"unverified input provenance: {item.get('path')}")
                try:
                    target = inside(root, root / str(item["path"]))
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if not target.is_file():
                    errors.append(f"input file missing: {item['path']}")
                elif sha256(target).lower() != str(item["sha256"]).lower():
                    errors.append(f"input hash mismatch: {item['path']}")
    if semantic is not None:
        if not nonempty(semantic.get("top_level_questions")):
            errors.append("semantic contract has no top-level questions")
        if not nonempty(semantic.get("scoring_or_objectives")):
            errors.append("semantic contract has no scoring/objective record")
        conflicts = semantic.get("unresolved_conflicts")
        if not isinstance(conflicts, list):
            errors.append("semantic contract unresolved_conflicts must be a list")
        elif conflicts:
            errors.append(f"semantic contract has {len(conflicts)} unresolved conflicts")
        if not nonempty(semantic.get("authority_order")):
            errors.append("semantic contract has no authority order")
    errors.extend(verify_freeze(root, "problem")["errors"])
    problem_freeze = freeze_path(root, "problem")
    if problem_freeze.is_file():
        try:
            frozen = {item["path"] for item in read_json(problem_freeze).get("files", []) if isinstance(item, dict)}
            required = {
                "00_admin/rules.json", "00_admin/input_manifest.json",
                "00_admin/semantic_contract.json", "01_problem/PROBLEM_BRIEF.md",
            }
            for required_path in sorted(required):
                if required_path not in frozen:
                    errors.append(f"problem freeze omits {required_path}")
        except Exception as exc:
            errors.append(f"cannot inspect problem freeze: {exc}")
    return result("rules-problem", errors)


def check_retrieval(root: Path) -> dict[str, Any]:
    errors = list(check_rules_problem(root)["errors"])
    data = load_required(root, "02_retrieval/retrieval_manifest.json", errors)
    if data is None:
        return result("retrieval", errors)
    if data.get("status") != "PASS":
        errors.append("retrieval manifest status is not PASS")
    kb = data.get("kb")
    if not isinstance(kb, dict) or kb.get("status") != "PASS" or not nonempty(kb.get("root")):
        errors.append("knowledge-base status/root is not verified")
    problems = data.get("problems")
    if not isinstance(problems, list) or not problems:
        errors.append("retrieval manifest has no problem entries")
        return result("retrieval", errors)
    documents: set[str] = set()
    required_groups = {"domain", "method", "validation"}
    for problem in problems:
        pid = str(problem.get("id", "<unknown>")) if isinstance(problem, dict) else "<invalid>"
        if not isinstance(problem, dict):
            errors.append("retrieval problem entry is not an object")
            continue
        queries = problem.get("queries")
        groups: set[str] = set()
        if isinstance(queries, list):
            for query in queries:
                if isinstance(query, dict):
                    group = query.get("group")
                    if isinstance(group, str):
                        groups.add(group)
                    if not nonempty(query.get("query")) or not nonempty(query.get("refs")):
                        errors.append(f"{pid}: query lacks text or refs")
        missing_groups = required_groups - groups
        if missing_groups:
            errors.append(f"{pid}: missing query groups {sorted(missing_groups)}")
        evidence = problem.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{pid}: no evidence cards")
            continue
        for card in evidence:
            if not isinstance(card, dict):
                errors.append(f"{pid}: evidence card is not an object")
                continue
            for field in ("ref", "document", "role", "abstraction", "applies_to", "risk"):
                if not nonempty(card.get(field)):
                    errors.append(f"{pid}: evidence card lacks {field}")
            if nonempty(card.get("document")):
                documents.add(str(card["document"]))
    minimum_docs = 3
    workflow = root / "00_admin/workflow.json"
    if workflow.is_file():
        try:
            minimum_docs = int(read_json(workflow).get("quality", {}).get("minimum_unique_documents", 3))
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    if len(documents) < minimum_docs:
        errors.append(f"only {len(documents)} unique evidence documents; require {minimum_docs}")
    return result("retrieval", errors)


def check_protocol(root: Path) -> dict[str, Any]:
    errors = list(check_retrieval(root)["errors"])
    data = load_required(root, "03_model/tournament_protocol.json", errors)
    if data is None:
        return result("protocol", errors)
    if data.get("status") != "PASS":
        errors.append("tournament protocol status is not PASS")
    try:
        minimum = int(data.get("minimum_candidates", 3))
    except (TypeError, ValueError):
        minimum = 0
    if minimum < 2:
        errors.append("minimum_candidates must be at least 2")
    problems = data.get("problems")
    if not isinstance(problems, list) or not problems:
        errors.append("tournament protocol has no problem entries")
        return result("protocol", errors)
    required = (
        "primary_metric", "direction", "constraints", "data_split", "seed_policy",
        "budget", "tie_breaker", "failure_rule",
    )
    for problem in problems:
        if not isinstance(problem, dict):
            errors.append("protocol problem entry is not an object")
            continue
        pid = str(problem.get("id", "<unknown>"))
        for field in required:
            if not nonempty(problem.get(field)):
                errors.append(f"{pid}: protocol lacks {field}")
        candidates = problem.get("candidates")
        if not isinstance(candidates, list) or len(candidates) < minimum:
            count = len(candidates) if isinstance(candidates, list) else 0
            errors.append(f"{pid}: {count} candidates; require {minimum}")
            continue
        ids = [str(item.get("id", "")) for item in candidates if isinstance(item, dict)]
        if len(ids) != len(candidates) or len(set(ids)) != len(ids) or any(not item for item in ids):
            errors.append(f"{pid}: candidate ids are missing or duplicated")
        if not any(isinstance(item, dict) and item.get("kind") == "baseline" for item in candidates):
            errors.append(f"{pid}: no baseline candidate")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                errors.append(f"{pid}: candidate is not an object")
                continue
            for field in ("method", "assumptions", "complexity", "failure_modes"):
                if not nonempty(candidate.get(field)):
                    errors.append(f"{pid}/{candidate.get('id', '?')}: lacks {field}")
            if not nonempty(candidate.get("kbrefs")) and not nonempty(candidate.get("derivation")):
                errors.append(f"{pid}/{candidate.get('id', '?')}: lacks kbrefs or original derivation")
    return result("protocol", errors)


def freeze_path(root: Path, stage: str) -> Path:
    return root / "00_admin" / "freezes" / f"{stage}.json"


def verify_freeze(root: Path, stage: str) -> dict[str, Any]:
    errors: list[str] = []
    path = freeze_path(root, stage)
    data = load_required(root, rel(root, path), errors)
    if data is None:
        return result(f"freeze:{stage}", errors)
    if data.get("status") != "PASS" or data.get("stage") != stage:
        errors.append(f"freeze {stage} metadata is not PASS/consistent")
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        errors.append(f"freeze {stage} contains no files")
        return result(f"freeze:{stage}", errors)
    expected_dependency = FREEZE_DEPENDENCY.get(stage)
    dependencies = data.get("dependencies")
    if expected_dependency is None:
        if dependencies not in ([], None):
            errors.append(f"freeze {stage} has unexpected dependencies")
    else:
        if not isinstance(dependencies, list) or len(dependencies) != 1:
            errors.append(f"freeze {stage} must bind dependency {expected_dependency}")
        else:
            dependency = dependencies[0]
            dependency_path = freeze_path(root, expected_dependency)
            if not dependency_path.is_file():
                errors.append(f"dependent freeze missing: {expected_dependency}")
            elif not isinstance(dependency, dict) or dependency.get("stage") != expected_dependency:
                errors.append(f"freeze {stage} dependency metadata is invalid")
            elif sha256(dependency_path) != dependency.get("manifest_sha256"):
                errors.append(f"freeze {stage} dependency changed: {expected_dependency}")
            else:
                upstream = verify_freeze(root, expected_dependency)
                errors.extend(f"upstream {expected_dependency}: {message}" for message in upstream["errors"])
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"freeze {stage} has invalid file entry")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append(f"freeze {stage} has entry without path")
            continue
        if relative in seen:
            errors.append(f"freeze {stage} duplicates {relative}")
        seen.add(relative)
        try:
            target = inside(root, root / relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not target.is_file():
            errors.append(f"frozen file missing: {relative}")
            continue
        actual = sha256(target)
        if actual != entry.get("sha256"):
            errors.append(f"frozen file changed: {relative}")
        if target.stat().st_size != entry.get("size"):
            errors.append(f"frozen file size changed: {relative}")
    return result(f"freeze:{stage}", errors)


def check_tournament(root: Path) -> dict[str, Any]:
    errors = list(check_protocol(root)["errors"])
    errors.extend(verify_freeze(root, "tournament_protocol")["errors"])
    protocol = load_required(root, "03_model/tournament_protocol.json", errors)
    metrics = load_required(root, "05_results/metrics.json", errors)
    tournament = load_required(root, "05_results/tournament.json", errors)
    if not protocol or not metrics or not tournament:
        return result("tournament", errors)
    if metrics.get("status") != "PASS":
        errors.append("metrics status is not PASS")
    if tournament.get("status") != "PASS":
        errors.append("tournament status is not PASS")
    runs = metrics.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("metrics has no runs")
        runs = []
    run_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for run in runs:
        if not isinstance(run, dict):
            errors.append("metrics run is not an object")
            continue
        key = (str(run.get("problem_id", "")), str(run.get("candidate_id", "")))
        run_index.setdefault(key, []).append(run)
        manifest = run.get("run_manifest")
        if not isinstance(manifest, str) or not (root / manifest).is_file():
            errors.append(f"run {run.get('run_id', '?')} has no valid run_manifest")
    protocol_by_id = {str(p.get("id")): p for p in protocol.get("problems", []) if isinstance(p, dict)}
    tournament_by_id = {str(p.get("id")): p for p in tournament.get("problems", []) if isinstance(p, dict)}
    if set(protocol_by_id) != set(tournament_by_id):
        errors.append("tournament problem ids do not match frozen protocol")
    for pid, spec in protocol_by_id.items():
        expected = {str(c.get("id")) for c in spec.get("candidates", []) if isinstance(c, dict)}
        outcome = tournament_by_id.get(pid, {})
        evaluated = set(map(str, outcome.get("evaluated_candidates", [])))
        if expected != evaluated:
            errors.append(f"{pid}: evaluated candidates do not exactly match protocol")
        winner = str(outcome.get("winner_id", ""))
        if winner not in expected:
            errors.append(f"{pid}: winner is not a registered candidate")
        winner_runs = run_index.get((pid, winner), [])
        if not any(r.get("status") == "PASS" and r.get("constraints_status") == "PASS" for r in winner_runs):
            errors.append(f"{pid}: winner has no feasible PASS run")
        for cid in expected:
            if (pid, cid) not in run_index:
                errors.append(f"{pid}/{cid}: no recorded run, including failure evidence")
        if outcome.get("robustness_status") != "PASS":
            errors.append(f"{pid}: robustness_status is not PASS")
        if outcome.get("ablation_status") not in {"PASS", "NOT_APPLICABLE"}:
            errors.append(f"{pid}: ablation status is neither PASS nor NOT_APPLICABLE")
        if outcome.get("ablation_status") == "NOT_APPLICABLE" and not nonempty(outcome.get("ablation_reason")):
            errors.append(f"{pid}: ablation exception lacks reason")
    return result("tournament", errors)


def check_model_results(root: Path) -> dict[str, Any]:
    errors = list(check_tournament(root)["errors"])
    freeze = verify_freeze(root, "model_results")
    errors.extend(freeze["errors"])
    required = {
        "03_model/ANALYSIS_MODELING_REPORT.md",
        "03_model/tournament_protocol.json",
        "05_results/metrics.json",
        "05_results/tournament.json",
        "05_results/RESULTS_REPORT.md",
    }
    path = freeze_path(root, "model_results")
    if path.is_file():
        try:
            frozen = {item["path"] for item in read_json(path).get("files", []) if isinstance(item, dict)}
            for required_path in sorted(required):
                if required_path not in frozen:
                    errors.append(f"model_results freeze omits {required_path}")
            if not any(item.startswith("04_code/") for item in frozen):
                errors.append("model_results freeze contains no 04_code files")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot inspect model_results freeze: {exc}")
    return result("model-results", errors)


def check_paper(root: Path) -> dict[str, Any]:
    errors = list(check_model_results(root)["errors"])
    errors.extend(verify_freeze(root, "paper")["errors"])
    freeze = freeze_path(root, "paper")
    if freeze.is_file():
        try:
            frozen = {item["path"] for item in read_json(freeze).get("files", []) if isinstance(item, dict)}
            if "06_paper/main.pdf" not in frozen:
                errors.append("paper freeze omits 06_paper/main.pdf")
            if not ({"06_paper/main.tex", "06_paper/main.typ"} & frozen):
                errors.append("paper freeze omits main.tex/main.typ")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot inspect paper freeze: {exc}")
    return result("paper", errors)


def evaluate_gate(root: Path, gate: str) -> dict[str, Any]:
    root = root.resolve()
    if gate == "rules-problem":
        return check_rules_problem(root)
    if gate == "retrieval":
        return check_retrieval(root)
    if gate == "protocol":
        return check_protocol(root)
    if gate == "tournament":
        return check_tournament(root)
    if gate == "model-results":
        return check_model_results(root)
    if gate == "paper":
        return check_paper(root)
    raise ValueError(f"unknown gate: {gate}")


def init_workspace(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    directories = (
        "00_admin/freezes", "00_admin/gates", "00_admin/handoffs", "00_admin/locks",
        "01_problem/original", "02_retrieval", "03_model", "04_code", "05_results/runs",
        "05_results/figure_data", "06_paper/sections", "06_paper/figures", "07_review",
    )
    for relative in directories:
        (root / relative).mkdir(parents=True, exist_ok=True)
    workflow_path = root / "00_admin/workflow.json"
    if not workflow_path.exists():
        atomic_json(workflow_path, {
            "schema_version": SCHEMA_VERSION,
            "profile": args.profile,
            "phase": "INIT",
            "competition": {"name": args.competition, "season": args.season},
            "paper": {"engine": args.engine, "language": args.language},
            "team_mode": args.team_mode,
            "kb": {"root": args.kb_root or "", "status": "NOT_RUN"},
            "quality": {"minimum_candidates": 3, "minimum_unique_documents": 3},
            "formal_data_classes": (
                ["official", "provided_example", "author_collected"]
                if args.profile == "formal"
                else ["official", "provided_example", "author_collected", "third_party_copy", "synthetic"]
            ),
            "created_at": now_iso(),
            "legacy_aliases": {},
        })
    templates: dict[str, dict[str, Any]] = {
        "00_admin/rules.json": {
            "schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "competition": args.competition,
            "season": args.season, "official_source": "", "retrieved_at": "",
            "template": {"status": "NOT_RUN", "source": "", "sha256": ""},
            "ai_policy": {"status": "NOT_RUN", "source": "", "summary": ""},
            "submission_requirements": {"status": "NOT_RUN", "source": "", "summary": ""},
        },
        "00_admin/input_manifest.json": {"schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "files": []},
        "00_admin/semantic_contract.json": {
            "schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "authority_order": [],
            "top_level_questions": [], "scoring_or_objectives": [], "units": [],
            "assumptions": [], "unresolved_conflicts": [],
        },
        "02_retrieval/retrieval_manifest.json": {
            "schema_version": SCHEMA_VERSION, "status": "NOT_RUN",
            "kb": {"root": args.kb_root or "", "checked_at": "", "status": "NOT_RUN"}, "problems": [],
        },
        "03_model/tournament_protocol.json": {
            "schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "minimum_candidates": 3, "problems": [],
        },
        "05_results/metrics.json": {"schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "data_class": "", "runs": []},
        "05_results/tournament.json": {"schema_version": SCHEMA_VERSION, "status": "NOT_RUN", "problems": []},
    }
    for relative, payload in templates.items():
        path = root / relative
        if not path.exists():
            atomic_json(path, payload)
    text_templates = {
        "00_admin/DECISIONS.md": "# 决策记录\n\n按时间记录题意、规则、接口和解冻裁决。\n",
        "00_admin/TEAM.md": (
            "# 四 Agent 分工\n\n| 角色 | Agent/负责人 | worktree/分支 | 独占范围 | 状态 |\n"
            "| --- | --- | --- | --- | --- |\n| O 总控 | 待填 | 待填 | 00_admin, 07_review | NOT_RUN |\n"
            "| M 建模 | 待填 | 待填 | 01_problem, 02_retrieval, 03_model | NOT_RUN |\n"
            "| E 计算 | 待填 | 待填 | 04_code, 05_results | NOT_RUN |\n"
            "| W 写作 | 待填 | 待填 | 06_paper | NOT_RUN |\n"
        ),
        "00_admin/AI_USE_LOG.md": (
            "# AI 使用记录\n\n按当届规则记录并由人工复核；不要把本模板当作已完成披露。\n\n"
            "| 时间 | 工具/模型 | 用途 | 输入范围 | 输出如何核验 | 人工复核者 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
        ),
        "plan.md": "# 方案（人类视图）\n\n唯一机器状态见 `00_admin/workflow.json`。\n",
        "todo.md": (
            "# 待办（人类视图）\n\n- [ ] 知识库检索门禁\n- [ ] 对擂协议冻结\n"
            "- [ ] 候选对擂\n- [ ] 模型与结果冻结\n- [ ] 论文冻结\n- [ ] 硬验收\n"
        ),
    }
    for relative, body in text_templates.items():
        path = root / relative
        if not path.exists():
            path.write_text(body, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "workspace": str(root), "workflow": str(workflow_path)}, ensure_ascii=False))
    return 0


def freeze(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    paths = iter_files(root, args.paths)
    if not paths:
        raise ValueError("freeze contains no files")
    target = freeze_path(root, args.stage)
    if target.exists() and not args.replace:
        raise FileExistsError(f"freeze already exists; use a documented change request then --replace: {target}")
    if target.exists() and args.replace and not args.change_request:
        raise ValueError("replacing a freeze requires --change-request")
    dependency_stage = FREEZE_DEPENDENCY[args.stage]
    dependencies: list[dict[str, str]] = []
    if dependency_stage is not None:
        dependency_path = freeze_path(root, dependency_stage)
        dependency_check = verify_freeze(root, dependency_stage)
        if dependency_check["status"] != "PASS":
            raise ValueError(f"cannot freeze {args.stage}; dependency {dependency_stage} is not valid")
        dependencies.append({"stage": dependency_stage, "manifest_sha256": sha256(dependency_path)})
    entries = [{"path": rel(root, path), "size": path.stat().st_size, "sha256": sha256(path)} for path in paths]
    atomic_json(target, {
        "schema_version": SCHEMA_VERSION, "stage": args.stage, "status": "PASS",
        "created_at": now_iso(), "actor": args.actor, "change_request": args.change_request or None,
        "dependencies": dependencies, "files": entries,
    })
    print(json.dumps({"status": "PASS", "stage": args.stage, "files": len(entries), "manifest": rel(root, target)}, ensure_ascii=False))
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    gate_result = evaluate_gate(root, args.gate)
    if args.record:
        atomic_json(root / "00_admin" / "gates" / f"{args.gate}.json", gate_result)
    print(json.dumps(gate_result, ensure_ascii=False, indent=2))
    return 0 if gate_result["status"] == "PASS" else 1


def command_verify_freeze(args: argparse.Namespace) -> int:
    freeze_result = verify_freeze(Path(args.workspace).resolve(), args.stage)
    print(json.dumps(freeze_result, ensure_ascii=False, indent=2))
    return 0 if freeze_result["status"] == "PASS" else 1


def command_status(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    snapshot = {gate: evaluate_gate(root, gate)["status"] for gate in GATES}
    print(json.dumps({"schema_version": SCHEMA_VERSION, "workspace": str(root), "gates": snapshot}, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    sub = value.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a non-destructive v3 workspace skeleton")
    init.add_argument("--workspace", default=".")
    init.add_argument("--competition", required=True)
    init.add_argument("--season", required=True)
    init.add_argument("--profile", choices=("formal", "practice"), default="formal")
    init.add_argument("--engine", choices=("latex", "typst"), default="latex")
    init.add_argument("--language", choices=("zh", "en"), default="zh")
    init.add_argument("--team-mode", choices=("four-agent", "single"), default="four-agent")
    init.add_argument("--kb-root", default="")
    init.set_defaults(handler=init_workspace)

    check = sub.add_parser("check", help="evaluate a gate and optionally record it")
    check.add_argument("--workspace", default=".")
    check.add_argument("--gate", choices=GATES, required=True)
    check.add_argument("--record", action="store_true")
    check.set_defaults(handler=command_check)

    freeze_cmd = sub.add_parser("freeze", help="create a SHA-256 freeze manifest")
    freeze_cmd.add_argument("--workspace", default=".")
    freeze_cmd.add_argument("--stage", choices=("problem", "tournament_protocol", "model_results", "paper"), required=True)
    freeze_cmd.add_argument("--actor", required=True)
    freeze_cmd.add_argument("--paths", nargs="+", required=True)
    freeze_cmd.add_argument("--replace", action="store_true")
    freeze_cmd.add_argument("--change-request", default="")
    freeze_cmd.set_defaults(handler=freeze)

    verify = sub.add_parser("verify-freeze", help="verify a freeze against current files")
    verify.add_argument("--workspace", default=".")
    verify.add_argument("--stage", choices=("problem", "tournament_protocol", "model_results", "paper"), required=True)
    verify.set_defaults(handler=command_verify_freeze)

    status = sub.add_parser("status", help="show all gate statuses")
    status.add_argument("--workspace", default=".")
    status.set_defaults(handler=command_status)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except Exception as exc:  # noqa: BLE001 - fail closed with concise diagnostics
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
